from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ai.common.schema import AiContractModel

ToolStatus = Literal[
    "SUCCESS",
    "NOT_FOUND",
    "INSUFFICIENT_DATA",
    "INVALID_ARGUMENT",
    "TOOL_ERROR",
]


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultView(AiContractModel):
    status: ToolStatus
    tool_name: str
    data: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    calculated_at: datetime
    error: dict[str, Any] | None = None
