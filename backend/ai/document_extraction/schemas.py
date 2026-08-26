from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedPayment(BaseModel):
    name: str
    amount: int | None = Field(default=None, ge=0)
    due_date: date | None = None
    status: Literal["PAID", "UNPAID", "UNKNOWN"]
    source_text: str


class CancellationTerm(BaseModel):
    summary: str
    source_text: str


class DocumentExtraction(BaseModel):
    document_type: Literal["WEDDING_HALL", "UNKNOWN"]
    company: str | None
    total_price: int | None = Field(default=None, ge=0)
    payments: list[ExtractedPayment]
    cancellation_terms: list[CancellationTerm]
    warnings: list[str]
