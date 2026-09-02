from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from ai.chat_agent.fallback import IntentDecision
from ai.chat_agent.intent import ChatIntent
from ai.common.types import ToolResultView
from app.application.chat_orchestration import ChatOrchestrationService

NOW = datetime(2026, 9, 3, 1, 2, 3, tzinfo=UTC)
USER_ID = UUID(int=1)
CONTRACT_ID = UUID(int=2)


class StubRegistry:
    def __init__(self, result: ToolResultView) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, object], UUID]] = []

    def resolve_contract_id(self, _message: str, _user_id: UUID) -> UUID:
        return CONTRACT_ID

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        user_id: UUID,
    ) -> ToolResultView:
        self.calls.append((tool_name, arguments, user_id))
        return self.result


def _service(
    intent: ChatIntent,
    arguments: dict[str, object],
    result: ToolResultView,
) -> tuple[ChatOrchestrationService, StubRegistry]:
    registry = StubRegistry(result)
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(demo_user_id=USER_ID),
        classifier=lambda _message: IntentDecision(intent, arguments),
        tool_registry=registry,  # type: ignore[arg-type]
    )
    return service, registry


def test_chat_01_04_schedule_answer_preserves_tool_date_amount_and_evidence() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getUpcomingPayments",
        data={
            "payments": [
                {
                    "contractId": str(CONTRACT_ID),
                    "company": "A웨딩홀",
                    "name": "잔금",
                    "amount": 20_000_000,
                    "dueDate": "2027-04-30",
                    "status": "UNPAID",
                }
            ]
        },
        evidence=[
            {
                "contractId": str(CONTRACT_ID),
                "label": "A웨딩홀 · 잔금",
                "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지",
            }
        ],
        calculated_at=NOW,
        error=None,
    )
    service, registry = _service(ChatIntent.SCHEDULE, {"limit": 1}, result)

    response = service.process("가장 가까운 잔금일은 언제야?")

    assert registry.calls == [("getUpcomingPayments", {"limit": 1}, USER_ID)]
    assert "2027-04-30" in response.answer
    assert "20,000,000원" in response.answer
    assert response.citations[0].source_text.startswith("잔금 20,000,000원")


def test_chat_02_05_finance_answer_and_calculation_use_identical_values() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getFinanceSummary",
        data={
            "availableAsset": 30_000_000,
            "remainingExpense": 20_000_000,
            "expectedBalance": 10_000_000,
        },
        evidence=[],
        calculated_at=NOW,
        error=None,
    )
    service, registry = _service(ChatIntent.FINANCE_SUMMARY, {}, result)

    response = service.process("남은 금액은 얼마야?")

    assert registry.calls == [("getFinanceSummary", {}, USER_ID)]
    assert "20,000,000원" in response.answer
    assert response.calculation is not None
    assert response.calculation.remaining_expense == 20_000_000


def test_contract_question_resolves_single_contract_before_tool_call() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getContractDetails",
        data={
            "company": "A웨딩홀",
            "totalPrice": 23_000_000,
            "cancellationTerms": [],
        },
        evidence=[],
        calculated_at=NOW,
        error=None,
    )
    service, registry = _service(ChatIntent.CONTRACT, {}, result)

    response = service.process("웨딩홀 계약 총액 알려줘")

    assert registry.calls == [("getContractDetails", {"contractId": str(CONTRACT_ID)}, USER_ID)]
    assert response.answer == "A웨딩홀 계약 총액은 23,000,000원입니다."


def test_chat_07_09_tool_failure_does_not_expose_or_invent_values() -> None:
    result = ToolResultView(
        status="TOOL_ERROR",
        tool_name="getFinanceSummary",
        data=None,
        evidence=[],
        calculated_at=NOW,
        error={"message": "internal details must not be exposed"},
    )
    service, _registry = _service(ChatIntent.FINANCE_SUMMARY, {}, result)

    response = service.process("남은 금액은 얼마야?")

    assert response.answer_type.value == "NOT_FOUND"
    assert response.calculation is None
    assert response.citations == []
    assert "internal details" not in response.answer
    assert not any(character.isdigit() for character in response.answer)
