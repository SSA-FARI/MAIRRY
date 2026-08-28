from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.documents.schemas import DocumentDetailResponse, DocumentUploadResponse
from app.domains.documents.service import (
    DocumentQueryService,
    DocumentUploadService,
    build_document_detail_response,
    get_document_query_service,
    get_document_upload_service,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    service: DocumentUploadService = Depends(get_document_upload_service),
) -> DocumentUploadResponse:
    document = await service.upload(db, file)
    return DocumentUploadResponse(
        id=document.id,
        original_name=document.original_filename,
        status=document.analysis_status,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    service: DocumentQueryService = Depends(get_document_query_service),
) -> DocumentDetailResponse:
    document = service.get(db, document_id)
    return build_document_detail_response(document)


@router.post("/{document_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def analyze_document(document_id: str) -> dict[str, str]:
    return {"documentId": document_id, "status": "PROCESSING"}


@router.put("/{document_id}/confirm")
def confirm_document(document_id: str) -> dict[str, str]:
    return {"documentId": document_id, "status": "CONFIRMED"}
