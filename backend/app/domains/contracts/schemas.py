from datetime import date
from uuid import UUID

from pydantic import Field, field_validator

from app.core.enums import ContractStatus, DocumentType, PaymentStatus
from app.core.schema import ApiModel


class ConfirmedPaymentInput(ApiModel):
    name: str = Field(min_length=1)
    amount: int = Field(ge=0)
    due_date: date | None
    status: PaymentStatus
    source_text: str | None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value


class ConfirmedCancellationTermInput(ApiModel):
    summary: str = Field(min_length=1)
    source_text: str | None

    @field_validator("summary")
    @classmethod
    def summary_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("summary must not be blank")
        return value


class ContractConfirm(ApiModel):
    document_type: DocumentType
    company: str = Field(min_length=1)
    total_price: int = Field(ge=0)
    payments: list[ConfirmedPaymentInput] = Field(min_length=1)
    cancellation_terms: list[ConfirmedCancellationTermInput]

    @field_validator("company")
    @classmethod
    def company_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("company must not be blank")
        return value


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
