import logging
import os
import tempfile
import uuid
from pathlib import Path

import anyio.to_thread
from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from ai.common.exceptions import AiOutputError, AiProviderError
from ai.document_extraction.schemas import DocumentAnalysisResult
from app.application.document_analysis import run_document_analysis
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AnalysisSource, DocumentStatus
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorBody
from app.domains.documents.models import Document
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.schemas import (
    DocumentDetailResponse,
    DocumentExtractionResponse,
    DocumentPreviewUrlResponse,
)
from app.domains.documents.storage import DocumentStoragePort
from app.domains.documents.transitions import ensure_transition_allowed
from app.domains.documents.validation import (
    ensure_signature_matches,
    read_upload_within_limit,
    resolve_expected_content_type,
)
from app.domains.wedding_plan.repository import WeddingPlanRepository
from app.integrations.storage.document_storage import MinioDocumentStorage, build_storage_key

logger = logging.getLogger(__name__)

_SOURCE_VISIBLE_STATUSES = frozenset({DocumentStatus.REVIEW_REQUIRED, DocumentStatus.CONFIRMED})
_EXTRACTION_VISIBLE_STATUSES = frozenset({DocumentStatus.REVIEW_REQUIRED, DocumentStatus.CONFIRMED})
_ERROR_VISIBLE_STATUSES = frozenset({DocumentStatus.FAILED})


def _resolve_document_scope(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """Use the current user's active plan, falling back to configured setup IDs."""
    plans = WeddingPlanRepository(db)
    plan = plans.get_current_for_user(settings.demo_user_id)
    if plan is None:
        return settings.demo_wedding_plan_id, settings.demo_member_id

    member = plans.get_member_for_user(plan.id, settings.demo_user_id)
    if member is None:
        return settings.demo_wedding_plan_id, settings.demo_member_id

    return plan.id, member.id


class DocumentUploadService:
    def __init__(self, repository: DocumentRepository, storage: DocumentStoragePort) -> None:
        self._repository = repository
        self._storage = storage

    async def upload(self, db: Session, file: UploadFile) -> Document:
        original_filename = file.filename or "unnamed"
        content_type = resolve_expected_content_type(original_filename)
        content = await read_upload_within_limit(file, settings.max_upload_size_bytes)
        ensure_signature_matches(content, content_type)

        wedding_plan_id, member_id = _resolve_document_scope(db)
        document_id = uuid.uuid4()
        storage_key = build_storage_key(document_id, original_filename)
        file_url = self._storage.save(storage_key, content, content_type)

        document = Document(
            id=document_id,
            wedding_plan_id=wedding_plan_id,
            uploaded_by_member_id=member_id,
            original_filename=original_filename,
            file_url=file_url,
            content_type=content_type,
        )
        created = self._repository.create(db, document)
        db.commit()
        db.refresh(created)
        return created


def get_document_upload_service() -> DocumentUploadService:
    return DocumentUploadService(
        repository=DocumentRepository(),
        storage=MinioDocumentStorage(),
    )


class DocumentQueryService:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    def get(self, db: Session, document_id: uuid.UUID) -> Document:
        wedding_plan_id, _member_id = _resolve_document_scope(db)
        document = self._repository.get_by_id(db, document_id, wedding_plan_id)
        if document is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="문서를 찾을 수 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return document


def get_document_query_service() -> DocumentQueryService:
    return DocumentQueryService(repository=DocumentRepository())


class DocumentPreviewService:
    def __init__(self, query_service: DocumentQueryService, storage: DocumentStoragePort) -> None:
        self._query_service = query_service
        self._storage = storage

    def build_preview_url(self, db: Session, document_id: uuid.UUID) -> DocumentPreviewUrlResponse:
        """Confirms the document belongs to the current wedding plan (via DocumentQueryService's
        404-on-mismatch scoping) before signing a URL, so no other user's private object can be
        previewed even if its id is guessed."""
        document = self._query_service.get(db, document_id)
        url, expires_at = self._storage.build_preview_url(document.file_url)
        return DocumentPreviewUrlResponse(url=url, expires_at=expires_at)


def get_document_preview_service() -> DocumentPreviewService:
    return DocumentPreviewService(
        query_service=DocumentQueryService(repository=DocumentRepository()),
        storage=MinioDocumentStorage(),
    )


class DocumentAnalysisService:
    """Accepts an analyze request synchronously; runs the AI call in a background task.

    process() is async def so BackgroundTasks awaits it directly on the event loop instead of
    running it in a worker thread. run_document_analysis (an async AI call) is awaited in
    place, with no asyncio.run() spinning up a throwaway loop per call. Every blocking step
    (storage read, disk write, db round-trips) is pushed onto a worker thread via
    anyio.to_thread.run_sync instead, so the event loop is never blocked by them.
    """

    def __init__(self, repository: DocumentRepository, storage: DocumentStoragePort) -> None:
        self._repository = repository
        self._storage = storage

    def start(self, db: Session, document_id: uuid.UUID) -> Document:
        """Locks the row (SELECT ... FOR UPDATE) so a concurrent analyze request on the same
        document blocks until this transaction commits, instead of both racing past the
        UPLOADED/FAILED check and starting duplicate AI calls."""
        wedding_plan_id, _member_id = _resolve_document_scope(db)
        document = self._repository.get_by_id(db, document_id, wedding_plan_id, for_update=True)
        if document is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="문서를 찾을 수 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        ensure_transition_allowed(document.analysis_status, DocumentStatus.PROCESSING)
        document.analysis_status = DocumentStatus.PROCESSING
        document.analysis_error = None
        db.commit()
        db.refresh(document)
        return document

    async def process(self, document_id: uuid.UUID) -> None:
        """Own DB session: runs after the request/response cycle via BackgroundTasks."""
        db = SessionLocal()
        try:
            wedding_plan_id, _member_id = _resolve_document_scope(db)
            document = await anyio.to_thread.run_sync(
                self._repository.get_by_id, db, document_id, wedding_plan_id
            )
            if document is None:
                return

            try:
                await self._run_analysis(db, document)
            except Exception as exc:
                error = self._build_failure_error(exc)
                logger.exception(
                    "Document analysis failed: documentId=%s errorCode=%s",
                    document_id,
                    error.code,
                )
                await anyio.to_thread.run_sync(db.rollback)
                await anyio.to_thread.run_sync(self._mark_failed, document_id, error)
        finally:
            await anyio.to_thread.run_sync(db.close)

    @staticmethod
    def _build_failure_error(exc: Exception) -> ErrorBody:
        """Maps an analysis failure to a user-facing ErrorBody. Never echoes exception
        internals (message text stays generic; details are intentionally empty) so stack
        traces or provider payloads cannot leak through the API."""
        if isinstance(exc, AppError):
            return ErrorBody(code=exc.code, message=exc.message)
        if isinstance(exc, AiProviderError | AiOutputError):
            return ErrorBody(
                code=ErrorCode.AI_PROVIDER_ERROR,
                message="AI 분석에 실패했습니다. 다시 시도해 주세요.",
            )
        return ErrorBody(code=ErrorCode.INTERNAL_ERROR, message="일시적인 오류가 발생했습니다.")

    async def _run_analysis(self, db: Session, document: Document) -> None:
        """Any failure here (storage, disk, AI, parsing) is caught by process() as FAILED."""
        content = await anyio.to_thread.run_sync(self._storage.read, document.file_url)

        suffix = Path(document.original_filename).suffix
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=suffix)
        os.close(temp_fd)
        temp_path = Path(temp_path_str)
        try:
            await anyio.to_thread.run_sync(temp_path.write_bytes, content)
            result = await run_document_analysis(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

        await anyio.to_thread.run_sync(self._store_result, db, document.id, result)

    @staticmethod
    def _store_result(db: Session, document_id: uuid.UUID, result: DocumentAnalysisResult) -> None:
        db.query(Document).filter(Document.id == document_id).update(
            {
                "extraction_raw": result.extraction.model_dump(mode="json"),
                "analysis_source": AnalysisSource(result.analysis_source),
                "analysis_status": DocumentStatus.REVIEW_REQUIRED,
            }
        )
        db.commit()

    @staticmethod
    def _mark_failed(document_id: uuid.UUID, error: ErrorBody) -> None:
        """Opens its own session instead of reusing process()'s session: if the failure that
        triggered this call was itself a broken DB connection, the just-rolled-back session
        may still be unusable, and recording FAILED must not depend on it recovering."""
        db = SessionLocal()
        try:
            db.query(Document).filter(Document.id == document_id).update(
                {
                    "analysis_status": DocumentStatus.FAILED,
                    "analysis_error": error.model_dump(mode="json"),
                }
            )
            db.commit()
        finally:
            db.close()


def get_document_analysis_service() -> DocumentAnalysisService:
    return DocumentAnalysisService(
        repository=DocumentRepository(),
        storage=MinioDocumentStorage(),
    )


def build_document_detail_response(document: Document) -> DocumentDetailResponse:
    document_status = document.analysis_status
    extraction = None
    if document_status in _EXTRACTION_VISIBLE_STATUSES and document.extraction_raw is not None:
        extraction = DocumentExtractionResponse.model_validate(document.extraction_raw)
    analysis_source = (
        document.analysis_source if document_status in _SOURCE_VISIBLE_STATUSES else None
    )
    error = None
    if document_status in _ERROR_VISIBLE_STATUSES and document.analysis_error is not None:
        error = ErrorBody.model_validate(document.analysis_error)
    return DocumentDetailResponse(
        id=document.id,
        original_name=document.original_filename,
        status=document_status,
        analysis_source=analysis_source,
        extraction=extraction,
        error=error,
    )
