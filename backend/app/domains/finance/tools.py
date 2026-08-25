from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel

ToolStatus = Literal[
    "SUCCESS",
    "NOT_FOUND",
    "INSUFFICIENT_DATA",
    "INVALID_ARGUMENT",
    "TOOL_ERROR",
]


class ToolResult(BaseModel):
    status: ToolStatus
    tool_name: str
    data: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    calculated_at: datetime
    error: dict[str, Any] | None


def success(tool_name: str, data: dict[str, Any]) -> ToolResult:
    return ToolResult(
        status="SUCCESS",
        tool_name=tool_name,
        data=data,
        evidence=[],
        calculated_at=datetime.now(timezone.utc),
        error=None,
    )

