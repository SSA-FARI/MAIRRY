from datetime import date

from pydantic import Field

from app.core.schema import ApiModel


class PaymentInput(ApiModel):
    amount: int = Field(ge=0)
    due_date: date | None = None
    status: str


class FinanceSummary(ApiModel):
    available_asset: int
    remaining_expense: int
    expected_balance: int


class SimulationRequest(ApiModel):
    name: str = Field(min_length=1)
    amount: int = Field(gt=0)


class SimulationResult(ApiModel):
    current_expected_balance: int
    simulated_expected_balance: int
    shortage_amount: int
