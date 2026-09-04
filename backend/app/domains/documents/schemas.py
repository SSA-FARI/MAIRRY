from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.core.enums import AnalysisSource, DocumentStatus, DocumentType, PaymentStatus
from app.core.errors import ErrorBody
from app.core.schema import ApiModel


class DocumentUploadResponse(ApiModel):
    id: UUID
    original_name: str
    status: DocumentStatus


class ExtractedPaymentResponse(ApiModel):
    name: str
    amount: int | None = Field(default=None, ge=0)
    due_date: date | None = None
    status: PaymentStatus
    source_text: str


class CancellationTermResponse(ApiModel):
    summary: str
    source_text: str


class DocumentExtractionResponse(ApiModel):
    document_type: DocumentType
    company: str | None = None
    total_price: int | None = Field(default=None, ge=0)
    payments: list[ExtractedPaymentResponse]
    cancellation_terms: list[CancellationTermResponse]
    warnings: list[str]


class DocumentPreviewUrlResponse(ApiModel):
    url: str
    expires_at: datetime


class DocumentDetailResponse(ApiModel):
    id: UUID
    original_name: str
    status: DocumentStatus
    analysis_source: AnalysisSource | None = None
    extraction: DocumentExtractionResponse | None = None
    error: ErrorBody | None = None
