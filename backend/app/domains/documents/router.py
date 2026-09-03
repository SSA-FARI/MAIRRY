from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ErrorResponse
from app.domains.contracts.schemas import ContractConfirm, ContractDetailRead
from app.domains.contracts.service import ContractConfirmationService
from app.domains.documents.schemas import (
    DocumentDetailResponse,
    DocumentPreviewUrlResponse,
    DocumentUploadResponse,
)
from app.domains.documents.service import (
    DocumentAnalysisService,
    DocumentPreviewService,
    DocumentQueryService,
    DocumentUploadService,
    build_document_detail_response,
    get_document_analysis_service,
    get_document_preview_service,
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


@router.post(
    "/{document_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentDetailResponse,
)
def analyze_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    service: DocumentAnalysisService = Depends(get_document_analysis_service),
) -> DocumentDetailResponse:
    document = service.start(db, document_id)
    background_tasks.add_task(service.process, document_id)
    return build_document_detail_response(document)


@router.get("/{document_id}/preview-url", response_model=DocumentPreviewUrlResponse)
def get_document_preview_url(
    document_id: UUID,
    db: Session = Depends(get_db),
    service: DocumentPreviewService = Depends(get_document_preview_service),
) -> DocumentPreviewUrlResponse:
    return service.build_preview_url(db, document_id)


@router.put(
    "/{document_id}/confirm",
    response_model=ContractDetailRead,
    responses={
        404: {"model": ErrorResponse, "description": "Document or wedding plan not found"},
        409: {"model": ErrorResponse, "description": "Invalid document state"},
        422: {"model": ErrorResponse, "description": "Invalid confirmation data"},
    },
)
def confirm_document(
    document_id: UUID,
    payload: ContractConfirm,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ContractDetailRead:
    return ContractConfirmationService(db, configuration).confirm(document_id, payload)
