from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.documents.schemas import DocumentUploadResponse
from app.domains.documents.service import DocumentUploadService, get_document_upload_service

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


@router.post("/{document_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def analyze_document(document_id: str) -> dict[str, str]:
    return {"documentId": document_id, "status": "PROCESSING"}


@router.put("/{document_id}/confirm")
def confirm_document(document_id: str) -> dict[str, str]:
    return {"documentId": document_id, "status": "CONFIRMED"}
