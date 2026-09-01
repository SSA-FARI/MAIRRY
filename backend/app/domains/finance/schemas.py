from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.core.enums import PaymentStatus
from app.core.schema import ApiModel


class PaymentInput(ApiModel):
    amount: int = Field(ge=0)
    due_date: date | None = None
    status: PaymentStatus


class FinancePayment(ApiModel):
    contract_id: UUID
    company: str
    name: str
    amount: int = Field(ge=0)
    due_date: date


class FinancePaymentRecord(ApiModel):
    payment_id: UUID
    contract_id: UUID
    company: str
    name: str
    amount: int = Field(ge=0)
    due_date: date | None
    created_at: datetime


class FinanceSummary(ApiModel):
    available_asset: int = Field(ge=0)
    remaining_expense: int = Field(ge=0)
    expected_balance: int
    nearest_payment: FinancePayment | None
    timeline: list[FinancePayment]


class SimulationRequest(ApiModel):
    name: str = Field(min_length=1)
    amount: int = Field(gt=0)


class SimulationResult(ApiModel):
    current_expected_balance: int
    simulated_expected_balance: int
    shortage_amount: int
