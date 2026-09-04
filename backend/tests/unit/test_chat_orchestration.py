import logging
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.schemas import IntentDecision
from ai.common.exceptions import AiOutputError, AiProviderTimeoutError
from ai.common.types import ToolResultView, ToolStatus
from ai.document_extraction.schemas import DocumentExtraction
from ai.providers.openai_provider import OpenAiProvider
from app.application.chat_orchestration import ChatOrchestrationService, _build_ai_provider

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


class StubAiProvider:
    def __init__(
        self,
        decision: IntentDecision | None = None,
        answer: str = "AI가 생성한 근거 기반 답변입니다.",
        *,
        classify_error: Exception | None = None,
        answer_error: Exception | None = None,
    ) -> None:
        self.decision = decision
        self.answer = answer
        self.classify_error = classify_error
        self.answer_error = answer_error
        self.classify_calls: list[str] = []
        self.answer_calls: list[tuple[str, ToolResultView]] = []

    async def extract_document(self, _file_path: Path) -> DocumentExtraction:
        raise NotImplementedError

    async def classify_intent(self, message: str) -> IntentDecision:
        self.classify_calls.append(message)
        if self.classify_error is not None:
            raise self.classify_error
        assert self.decision is not None
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

    service.process("A웨딩홀 잔금일 언제야?")

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


def _finance_result(status: ToolStatus = "SUCCESS") -> ToolResultView:
    return ToolResultView(
        status=status,
        tool_name="getFinanceSummary",
        data=(
            {
                "availableAsset": 30_000_000,
                "remainingExpense": 20_000_000,
                "expectedBalance": 10_000_000,
            }
            if status == "SUCCESS"
            else None
        ),
        evidence=[],
        calculated_at=NOW,
        error=None if status == "SUCCESS" else {"message": "private provider detail"},
    )


def test_configured_provider_classifies_and_generates_answer_from_tool_result() -> None:
    result = _finance_result()
    registry = StubRegistry(result)
    provider = StubAiProvider(
        IntentDecision(ChatIntent.FINANCE_SUMMARY, {}),
        answer="AI 답변: 예상 잔액은 10,000,000원입니다.",
    )
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(demo_user_id=USER_ID),
        tool_registry=registry,  # type: ignore[arg-type]
        ai_provider=provider,
    )

    response = service.process("현재 자금 상태를 설명해줘")

    assert provider.classify_calls == ["현재 자금 상태를 설명해줘"]
    assert provider.answer_calls == [("현재 자금 상태를 설명해줘", result)]
    assert registry.calls == [("getFinanceSummary", {}, USER_ID)]
    assert response.answer == "AI 답변: 예상 잔액은 10,000,000원입니다."
    assert response.calculation is not None
    assert response.calculation.expected_balance == 10_000_000


def test_provider_answer_cannot_replace_backend_contract_citation() -> None:
    evidence = {
        "contractId": str(CONTRACT_ID),
        "label": "A웨딩홀 · 계약",
        "sourceText": "계약 총액은 23,000,000원",
    }
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getContractDetails",
        data={
            "company": "A웨딩홀",
            "totalPrice": 23_000_000,
            "cancellationTerms": [],
        },
        evidence=[evidence],
        calculated_at=NOW,
        error=None,
    )
    registry = StubRegistry(result)
    provider = StubAiProvider(
        IntentDecision(ChatIntent.CONTRACT, {"contractId": str(CONTRACT_ID)}),
        answer="AI가 표현만 다듬은 계약 답변입니다.",
    )
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(demo_user_id=USER_ID),
        tool_registry=registry,  # type: ignore[arg-type]
        ai_provider=provider,
    )

    response = service.process("이 계약 내용을 설명해줘")

    assert response.answer == "AI가 표현만 다듬은 계약 답변입니다."
    assert len(response.citations) == 1
    assert response.citations[0].contract_id == CONTRACT_ID
    assert response.citations[0].source_text == evidence["sourceText"]


def test_provider_classification_failure_uses_deterministic_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = _finance_result()
    registry = StubRegistry(result)
    provider = StubAiProvider(classify_error=AiProviderTimeoutError("sensitive response"))
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(demo_user_id=USER_ID),
        classifier=lambda _message: IntentDecision(ChatIntent.FINANCE_SUMMARY, {}),
        tool_registry=registry,  # type: ignore[arg-type]
        ai_provider=provider,
    )

    with caplog.at_level(logging.WARNING):
        response = service.process("남은 금액은 얼마야?")

    assert "20,000,000원" in response.answer
    assert provider.answer_calls == []
    assert "AiProviderTimeoutError" in caplog.text
    assert "sensitive response" not in caplog.text
    assert "남은 금액은 얼마야?" not in caplog.text


def test_provider_answer_failure_preserves_deterministic_tool_evidence() -> None:
    result = _finance_result()
    registry = StubRegistry(result)
    provider = StubAiProvider(
        IntentDecision(ChatIntent.FINANCE_SUMMARY, {}),
        answer_error=AiOutputError("unsupported generated number"),
    )
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(demo_user_id=USER_ID),
        tool_registry=registry,  # type: ignore[arg-type]
        ai_provider=provider,
    )

    response = service.process("자금 현황을 자연스럽게 설명해줘")

    assert "현재 가용자금은 30,000,000원" in response.answer
    assert response.calculation is not None
    assert response.calculation.expected_balance == 10_000_000


def test_failed_tool_result_never_calls_provider_answer_generation() -> None:
    result = _finance_result("TOOL_ERROR")
    registry = StubRegistry(result)
    provider = StubAiProvider(IntentDecision(ChatIntent.FINANCE_SUMMARY, {}))
    service = ChatOrchestrationService(
        SimpleNamespace(),
        SimpleNamespace(demo_user_id=USER_ID),
        tool_registry=registry,  # type: ignore[arg-type]
        ai_provider=provider,
    )

    response = service.process("자금 현황 알려줘")

    assert response.answer_type.value == "NOT_FOUND"
    assert provider.answer_calls == []
    assert not any(character.isdigit() for character in response.answer)


@pytest.mark.parametrize(
    ("api_key", "model"),
    [("", ""), ("configured-key", ""), ("", "configured-model")],
)
def test_incomplete_ai_configuration_keeps_provider_disabled(api_key: str, model: str) -> None:
    configuration = SimpleNamespace(
        ai_api_key=api_key,
        ai_model=model,
        ai_timeout_seconds=45,
    )

    assert _build_ai_provider(configuration) is None  # type: ignore[arg-type]


def test_complete_ai_configuration_builds_openai_provider() -> None:
    configuration = SimpleNamespace(
        ai_api_key="configured-key",
        ai_model="configured-model",
        ai_timeout_seconds=12,
    )

    provider = _build_ai_provider(configuration)  # type: ignore[arg-type]

    assert isinstance(provider, OpenAiProvider)
