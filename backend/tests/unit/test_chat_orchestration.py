import asyncio
import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from ai.chat_agent.fallback import IntentDecision
from ai.chat_agent.intent import ChatIntent
from ai.common.exceptions import AiOutputError, AiProviderTimeoutError
from ai.common.types import ToolResultView
from ai.providers.base import ChatProvider
from app.application.chat_orchestration import ChatOrchestrationService
from app.core.errors import AppError

NOW = datetime(2026, 9, 3, 1, 2, 3, tzinfo=UTC)
USER_ID = UUID(int=1)
CONTRACT_ID = UUID(int=2)


class StubRegistry:
    def __init__(self, result: ToolResultView) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, object], UUID]] = []
        self.resolve_thread_ids: list[int] = []
        self.execute_thread_ids: list[int] = []

    def resolve_contract_id(self, _message: str, _user_id: UUID) -> UUID:
        self.resolve_thread_ids.append(threading.get_ident())
        return CONTRACT_ID

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        user_id: UUID,
    ) -> ToolResultView:
        self.execute_thread_ids.append(threading.get_ident())
        self.calls.append((tool_name, arguments, user_id))
        return self.result


class StubChatProvider:
    def __init__(
        self,
        decision: IntentDecision,
        *,
        answer: str = "AI가 생성한 근거 기반 답변입니다.",
        classify_error: Exception | None = None,
        answer_error: Exception | None = None,
    ) -> None:
        self.decision = decision
        self.answer = answer
        self.classify_error = classify_error
        self.answer_error = answer_error
        self.classify_calls: list[str] = []
        self.answer_calls: list[tuple[str, ToolResultView]] = []

    async def classify_intent(self, message: str) -> IntentDecision:
        self.classify_calls.append(message)
        if self.classify_error is not None:
            raise self.classify_error
        return self.decision

    async def generate_answer(self, message: str, result: ToolResultView) -> str:
        self.answer_calls.append((message, result))
        if self.answer_error is not None:
            raise self.answer_error
        return self.answer


def _service(
    intent: ChatIntent,
    arguments: dict[str, object],
    result: ToolResultView,
    *,
    provider: ChatProvider | None = None,
    enable_demo_fallback: bool = True,
) -> tuple[ChatOrchestrationService, StubRegistry]:
    registry = StubRegistry(result)
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(
            demo_user_id=USER_ID,
            enable_demo_fallback=enable_demo_fallback,
        ),
        classifier=lambda _message: IntentDecision(intent, arguments),
        provider=provider,
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

    response = asyncio.run(service.process("가장 가까운 잔금일은 언제야?"))

    assert registry.calls == [
        (
            "getUpcomingPayments",
            {"limit": 1, "contractId": str(CONTRACT_ID)},
            USER_ID,
        )
    ]
    assert "2027-04-30" in response.answer
    assert "20,000,000원" in response.answer
    assert response.citations[0].source_text.startswith("잔금 20,000,000원")


def test_schedule_question_resolves_company_to_contract_filter() -> None:
    result = ToolResultView(
        status="NOT_FOUND",
        tool_name="getUpcomingPayments",
        data=None,
        evidence=[],
        calculated_at=NOW,
        error={"message": "no payment"},
    )
    service, registry = _service(ChatIntent.SCHEDULE, {"limit": 1}, result)

    asyncio.run(service.process("A웨딩홀 잔금일 언제야?"))

    assert registry.calls == [
        (
            "getUpcomingPayments",
            {"limit": 1, "contractId": str(CONTRACT_ID)},
            USER_ID,
        )
    ]


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

    response = asyncio.run(service.process("남은 금액은 얼마야?"))

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

    response = asyncio.run(service.process("웨딩홀 계약 총액 알려줘"))

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

    response = asyncio.run(service.process("남은 금액은 얼마야?"))

    assert response.answer_type.value == "NOT_FOUND"
    assert response.calculation is None
    assert response.citations == []
    assert "internal details" not in response.answer
    assert not any(character.isdigit() for character in response.answer)


def test_live_provider_intent_and_answer_are_connected_without_replacing_evidence() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getUpcomingPayments",
        data={
            "payments": [
                {
                    "company": "A웨딩홀",
                    "name": "잔금",
                    "amount": 20_000_000,
                    "dueDate": "2027-04-30",
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
    provider = StubChatProvider(
        IntentDecision(ChatIntent.SCHEDULE, {"limit": 1}),
        answer="A웨딩홀 잔금일은 2027-04-30입니다.",
    )
    service, registry = _service(ChatIntent.UNKNOWN, {}, result, provider=provider)

    response = asyncio.run(service.process("가장 가까운 잔금일은 언제야?"))

    assert provider.classify_calls == ["가장 가까운 잔금일은 언제야?"]
    assert provider.answer_calls == [("가장 가까운 잔금일은 언제야?", result)]
    assert registry.calls[0][0] == "getUpcomingPayments"
    assert response.answer == "A웨딩홀 잔금일은 2027-04-30입니다."
    assert response.citations[0].source_text.startswith("잔금 20,000,000원")


def test_synchronous_tool_resolution_and_execution_run_in_one_worker_thread() -> None:
    result = ToolResultView(
        status="NOT_FOUND",
        tool_name="getUpcomingPayments",
        data=None,
        evidence=[],
        calculated_at=NOW,
        error={"message": "no payment"},
    )
    service, registry = _service(ChatIntent.SCHEDULE, {"limit": 1}, result)
    event_loop_thread_id: int | None = None

    async def invoke() -> None:
        nonlocal event_loop_thread_id
        event_loop_thread_id = threading.get_ident()
        await service.process("A웨딩홀 잔금일 언제야?")

    asyncio.run(invoke())

    assert event_loop_thread_id is not None
    assert registry.resolve_thread_ids == registry.execute_thread_ids
    assert registry.execute_thread_ids[0] != event_loop_thread_id


def test_provider_intent_failure_uses_rule_based_classifier() -> None:
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
    provider = StubChatProvider(
        IntentDecision(ChatIntent.UNKNOWN),
        classify_error=AiProviderTimeoutError("private provider detail"),
    )
    service, registry = _service(
        ChatIntent.FINANCE_SUMMARY,
        {},
        result,
        provider=provider,
    )

    response = asyncio.run(service.process("남은 금액은 얼마야?"))

    assert registry.calls == [("getFinanceSummary", {}, USER_ID)]
    assert provider.answer_calls == []
    assert "20,000,000원" in response.answer


def test_provider_answer_failure_keeps_deterministic_answer_and_calculation() -> None:
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
    provider = StubChatProvider(
        IntentDecision(ChatIntent.FINANCE_SUMMARY),
        answer_error=AiOutputError("private generated output"),
    )
    service, _registry = _service(
        ChatIntent.UNKNOWN,
        {},
        result,
        provider=provider,
    )

    response = asyncio.run(service.process("남은 금액은 얼마야?"))

    assert "20,000,000원" in response.answer
    assert response.calculation is not None
    assert response.calculation.expected_balance == 10_000_000


def test_failed_tool_result_does_not_call_answer_provider() -> None:
    result = ToolResultView(
        status="TOOL_ERROR",
        tool_name="getFinanceSummary",
        data=None,
        evidence=[],
        calculated_at=NOW,
        error={"message": "private tool detail"},
    )
    provider = StubChatProvider(IntentDecision(ChatIntent.FINANCE_SUMMARY))
    service, _registry = _service(
        ChatIntent.UNKNOWN,
        {},
        result,
        provider=provider,
    )

    response = asyncio.run(service.process("남은 금액은 얼마야?"))

    assert provider.answer_calls == []
    assert response.answer_type.value == "NOT_FOUND"


def test_disabled_fallback_returns_ai_provider_error() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getFinanceSummary",
        data={},
        evidence=[],
        calculated_at=NOW,
        error=None,
    )
    service, _registry = _service(
        ChatIntent.FINANCE_SUMMARY,
        {},
        result,
        enable_demo_fallback=False,
    )

    with pytest.raises(AppError) as error:
        asyncio.run(service.process("남은 금액은 얼마야?"))

    assert error.value.code.value == "AI_PROVIDER_ERROR"
    assert error.value.status_code == 502
