import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.documents.models import Document
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.storage import DocumentStoragePort, InterimLocalDocumentStorage
from app.domains.documents.validation import (
    ensure_signature_matches,
    read_upload_within_limit,
    resolve_expected_content_type,
)


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
        storage_key = f"{document_id}{Path(original_filename).suffix.lower()}"
        file_url = self._storage.save(storage_key, content, content_type)

        document = Document(
            id=document_id,
            wedding_plan_id=settings.demo_wedding_plan_id,
            uploaded_by_member_id=settings.demo_member_id,
            original_filename=original_filename,
            file_url=file_url,
            content_type=content_type,
        )
        return self._repository.create(db, document)


def get_document_upload_service() -> DocumentUploadService:
    return DocumentUploadService(
        repository=DocumentRepository(),
        storage=InterimLocalDocumentStorage(),
    )
