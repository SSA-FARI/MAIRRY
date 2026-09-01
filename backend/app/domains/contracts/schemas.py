from datetime import date
from uuid import UUID

from pydantic import Field

from app.core.enums import ContractStatus, DocumentType, PaymentStatus
from app.core.schema import ApiModel


class ConfirmedPaymentRead(ApiModel):
    name: str
    amount: int = Field(ge=0)
    due_date: date | None
    status: PaymentStatus
    source_text: str | None


class ConfirmedCancellationTermRead(ApiModel):
    summary: str
    source_text: str | None


class UpcomingPaymentRead(ApiModel):
    contract_id: UUID
    company: str
    name: str
    amount: int = Field(ge=0)
    due_date: date


class ContractSummaryRead(ApiModel):
    id: UUID
    company: str
    total_price: int = Field(ge=0)
    status: ContractStatus
    next_payment: UpcomingPaymentRead | None


class ContractListRead(ApiModel):
    items: list[ContractSummaryRead]


class ContractDetailRead(ApiModel):
    id: UUID
    document_id: UUID
    document_type: DocumentType
    company: str
    total_price: int = Field(ge=0)
    status: ContractStatus
    payments: list[ConfirmedPaymentRead] = Field(min_length=1)
    cancellation_terms: list[ConfirmedCancellationTermRead]
