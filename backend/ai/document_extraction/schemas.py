from datetime import date

from pydantic import BaseModel, Field


class ExtractedPayment(BaseModel):
    name: str
    amount: int | None = Field(default=None, ge=0)
    due_date: date | None = None
    status: str
    source_text: str


class CancellationTerm(BaseModel):
    summary: str
    source_text: str


class DocumentExtraction(BaseModel):
    document_type: str
    company: str | None
    total_price: int | None = Field(default=None, ge=0)
    payments: list[ExtractedPayment]
    cancellation_terms: list[CancellationTerm]
    warnings: list[str]
