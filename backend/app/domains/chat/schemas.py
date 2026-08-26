from typing import Any

from pydantic import Field

from app.core.enums import AnswerType
from app.core.schema import ApiModel


class ChatRequest(ApiModel):
    message: str = Field(min_length=1, max_length=2_000)


class ChatResponse(ApiModel):
    answer: str
    answer_type: AnswerType
    citations: list[dict[str, Any]]
    calculation: dict[str, Any] | None
