from datetime import date
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from ai.chat_agent.intent import ChatIntent
from ai.common.schema import AiContractModel


class IntentDecision(AiContractModel):
    """Validated model output for selecting one deterministic Backend Tool."""

    intent: ChatIntent
    contract_id: UUID | None
    from_date: date | None = Field(alias="from")
    to: date | None
    limit: int | None = Field(ge=1, le=100)
    name: str | None
    amount: int | None = Field(gt=0)

    def __init__(
        self,
        intent: ChatIntent | str | None = None,
        arguments: dict[str, Any] | None = None,
        **data: Any,
    ) -> None:
        """Keep the existing orchestration constructor while validating provider output."""
        if intent is not None:
            data["intent"] = intent
        if arguments is not None:
            data.update(arguments)
        for field_name in ("contractId", "from", "to", "limit", "name", "amount"):
            data.setdefault(field_name, None)
        super().__init__(**data)

    @model_validator(mode="after")
    def validate_arguments_for_intent(self) -> "IntentDecision":
        if self.from_date is not None and self.to is not None and self.from_date > self.to:
            raise ValueError("from must be on or before to")

        populated = {
            "contractId": self.contract_id,
            "from": self.from_date,
            "to": self.to,
            "limit": self.limit,
            "name": self.name,
            "amount": self.amount,
        }
        allowed = {
            ChatIntent.CONTRACT: {"contractId"},
            ChatIntent.SCHEDULE: {"contractId", "from", "to", "limit"},
            ChatIntent.FINANCE_SUMMARY: set(),
            ChatIntent.EXPENSE_SIMULATION: {"name", "amount"},
            ChatIntent.UNKNOWN: set(),
        }[self.intent]
        unexpected = {
            key for key, value in populated.items() if value is not None and key not in allowed
        }
        if unexpected:
            raise ValueError(f"arguments are not allowed for {self.intent}")
        if self.intent == ChatIntent.EXPENSE_SIMULATION and (
            self.name is None or not self.name.strip() or self.amount is None
        ):
            raise ValueError("expense simulation requires name and amount")
        return self

    @property
    def arguments(self) -> dict[str, Any]:
        values = {
            "contractId": str(self.contract_id) if self.contract_id is not None else None,
            "from": self.from_date.isoformat() if self.from_date is not None else None,
            "to": self.to.isoformat() if self.to is not None else None,
            "limit": self.limit,
            "name": self.name.strip() if self.name is not None else None,
            "amount": self.amount,
        }
        return {key: value for key, value in values.items() if value is not None}


class GeneratedAnswer(AiContractModel):
    answer: str = Field(min_length=1, max_length=2_000)
