from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator

from ai.rag.schemas import KnowledgeType
from app.core.enums import AnswerType
from app.core.schema import ApiModel


class ChatRequest(ApiModel):
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=2_000)
    history: list[Annotated[str, Field(max_length=2_000)]] = Field(
        default_factory=list, max_length=8
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class Citation(ApiModel):
    contract_id: UUID | None = None
    document_id: UUID | None = None
    source_type: KnowledgeType = KnowledgeType.CONTRACT_CLAUSE
    title: str | None = None
    clause_title: str | None = None
    page: int | None = Field(default=None, ge=1)
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
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    answer: str
    answer_type: AnswerType
    citations: list[Citation]
    calculation: FinanceCalculation | SimulationCalculation | None
    used_rag: bool = False
