from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.core.enums import AnswerType
from app.core.schema import ApiModel


class ChatRequest(ApiModel):
    message: str = Field(min_length=1, max_length=2_000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class Citation(ApiModel):
    contract_id: UUID
    label: str
    source_text: str


class Calculation(ApiModel):
    tool_name: str
    calculated_at: datetime


class FinanceCalculation(Calculation):
    available_asset: int = Field(ge=0)
    remaining_expense: int = Field(ge=0)
    expected_balance: int


class SimulationCalculation(Calculation):
    current_expected_balance: int
    simulated_expected_balance: int
    shortage_amount: int = Field(ge=0)


class ChatResponse(ApiModel):
    answer: str
    answer_type: AnswerType
    citations: list[Citation]
    calculation: FinanceCalculation | SimulationCalculation | None
