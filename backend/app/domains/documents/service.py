import uuid

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.documents.models import Document
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.schemas import DocumentDetailResponse, DocumentExtractionResponse
from app.domains.documents.storage import DocumentStoragePort
from app.domains.documents.validation import (
    ensure_signature_matches,
    read_upload_within_limit,
    resolve_expected_content_type,
)
from app.integrations.storage.document_storage import MinioDocumentStorage, build_storage_key

_SOURCE_VISIBLE_STATUSES = frozenset(
    {DocumentStatus.REVIEW_REQUIRED, DocumentStatus.FAILED, DocumentStatus.CONFIRMED}
)
_EXTRACTION_VISIBLE_STATUSES = frozenset({DocumentStatus.REVIEW_REQUIRED, DocumentStatus.CONFIRMED})


class DocumentUploadService:
    def __init__(self, repository: DocumentRepository, storage: DocumentStoragePort) -> None:
        self._repository = repository
        self._storage = storage

    async def upload(self, db: Session, file: UploadFile) -> Document:
        original_filename = file.filename or "unnamed"
        content_type = resolve_expected_content_type(original_filename)
        content = await read_upload_within_limit(file, settings.max_upload_size_bytes)
        ensure_signature_matches(content, content_type)

        document_id = uuid.uuid4()
        storage_key = build_storage_key(document_id, original_filename)
        file_url = self._storage.save(storage_key, content, content_type)

        document = Document(
            id=document_id,
            wedding_plan_id=settings.demo_wedding_plan_id,
            uploaded_by_member_id=settings.demo_member_id,
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
        document = self._repository.get_by_id(db, document_id, settings.demo_wedding_plan_id)
        if document is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="문서를 찾을 수 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return document


def get_document_query_service() -> DocumentQueryService:
    return DocumentQueryService(repository=DocumentRepository())


def build_document_detail_response(document: Document) -> DocumentDetailResponse:
    document_status = document.analysis_status
    extraction = None
    if document_status in _EXTRACTION_VISIBLE_STATUSES and document.extraction_raw is not None:
        extraction = DocumentExtractionResponse.model_validate(document.extraction_raw)
    analysis_source = (
        document.analysis_source if document_status in _SOURCE_VISIBLE_STATUSES else None
    )
    return DocumentDetailResponse(
        id=document.id,
        original_name=document.original_filename,
        status=document_status,
        analysis_source=analysis_source,
        extraction=extraction,
        error=None,
    )
