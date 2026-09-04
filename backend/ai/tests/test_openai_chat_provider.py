import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from ai.chat_agent.intent import ChatIntent
from ai.common.exceptions import AiOutputError, AiProviderInputError, AiProviderTimeoutError
from ai.common.types import ToolResultView
from ai.providers.openai_provider import OpenAiProvider


def _completed_response(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"status": "completed", "output_text": json.dumps(payload, ensure_ascii=False)},
    )


def _provider(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAiProvider:
    return OpenAiProvider(
        api_key="test-api-key",
        model="test-model",
        timeout_seconds=12,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _intent_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "intent": "FINANCE_SUMMARY",
        "contractId": None,
        "from": None,
        "to": None,
        "limit": None,
        "name": None,
        "amount": None,
    }
    payload.update(overrides)
    return payload


def _finance_result() -> ToolResultView:
    return ToolResultView(
        status="SUCCESS",
        tool_name="getFinanceSummary",
        data={
            "availableAsset": 30_000_000,
            "remainingExpense": 20_000_000,
            "expectedBalance": 10_000_000,
        },
        evidence=[],
        calculated_at=datetime(2026, 9, 4, tzinfo=UTC),
        error=None,
    )


def test_classify_intent_uses_strict_schema_and_returns_validated_arguments() -> None:
    captured_body: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content)
        return _completed_response(
            _intent_payload(
                intent="EXPENSE_SIMULATION",
                name="가전 비용",
                amount=3_000_000,
            )
        )

    provider = _provider(handler)
    try:
        decision = asyncio.run(provider.classify_intent("가전 비용 300만 원 추가해도 돼?"))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]

    assert decision.intent == ChatIntent.EXPENSE_SIMULATION
    assert decision.arguments == {"name": "가전 비용", "amount": 3_000_000}
    response_format = captured_body["text"]["format"]
    assert response_format["strict"] is True
    assert set(response_format["schema"]["required"]) == {
        "intent",
        "contractId",
        "from",
        "to",
        "limit",
        "name",
        "amount",
    }


def test_classify_intent_preserves_camel_case_contract_id() -> None:
    contract_id = "90af8db0-a099-40a0-bb92-720ec331a6a0"
    provider = _provider(
        lambda _request: _completed_response(
            _intent_payload(
                intent="SCHEDULE",
                contractId=contract_id,
                limit=1,
            )
        )
    )
    try:
        decision = asyncio.run(provider.classify_intent("이 계약의 잔금일은 언제야?"))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]

    assert str(decision.contract_id) == contract_id
    assert decision.arguments == {"contractId": contract_id, "limit": 1}


@pytest.mark.parametrize(
    "payload",
    [
        _intent_payload(intent="UNSUPPORTED"),
        _intent_payload(intent="EXPENSE_SIMULATION", name="가전 비용"),
        _intent_payload(intent="FINANCE_SUMMARY", amount=3_000_000),
        _intent_payload(intent="SCHEDULE", **{"from": "2027-05-01", "to": "2027-04-01"}),
    ],
)
def test_invalid_intent_output_is_rejected(payload: dict[str, Any]) -> None:
    provider = _provider(lambda _request: _completed_response(payload))
    try:
        with pytest.raises(AiOutputError, match="invalid intent decision"):
            asyncio.run(provider.classify_intent("질문"))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]


def test_blank_message_is_rejected_before_provider_request() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        pytest.fail("Provider request must not run for blank input")

    provider = _provider(handler)
    try:
        with pytest.raises(AiProviderInputError):
            asyncio.run(provider.classify_intent("   "))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]


def test_generate_answer_sends_safe_tool_result_and_accepts_grounded_values() -> None:
    captured_input = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_input
        body = json.loads(request.content)
        captured_input = body["input"][0]["content"][0]["text"]
        return _completed_response(
            {"answer": ("남은 확정지출은 20,000,000원이고 예상 잔액은 10,000,000원입니다.")}
        )

    provider = _provider(handler)
    try:
        answer = asyncio.run(provider.generate_answer("남은 금액은?", _finance_result()))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]

    assert "20,000,000원" in answer
    assert "error" not in json.loads(captured_input)["toolResult"]


def test_generate_answer_rejects_number_absent_from_tool_result() -> None:
    provider = _provider(
        lambda _request: _completed_response({"answer": "예상 잔액은 99,000,000원입니다."})
    )
    try:
        with pytest.raises(AiOutputError, match="outside the ToolResult"):
            asyncio.run(provider.generate_answer("남은 금액은?", _finance_result()))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]


def test_generate_answer_accepts_korean_date_without_leading_zeroes() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getUpcomingPayments",
        data={
            "payments": [
                {
                    "company": "A웨딩홀",
                    "name": "잔금",
                    "amount": 20_000_000,
                    "dueDate": "2026-09-04",
                }
            ]
        },
        evidence=[],
        calculated_at=datetime(2026, 9, 4, tzinfo=UTC),
        error=None,
    )
    provider = _provider(
        lambda _request: _completed_response({"answer": "A웨딩홀 잔금일은 2026년 9월 4일입니다."})
    )
    try:
        answer = asyncio.run(provider.generate_answer("잔금일은 언제야?", result))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]

    assert answer == "A웨딩홀 잔금일은 2026년 9월 4일입니다."


def test_generate_answer_rejects_failed_tool_result_without_request() -> None:
    result = _finance_result().model_copy(
        update={"status": "TOOL_ERROR", "data": None, "error": {"message": "private"}}
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        pytest.fail("Provider request must not run for failed ToolResult")

    provider = _provider(handler)
    try:
        with pytest.raises(AiProviderInputError):
            asyncio.run(provider.generate_answer("남은 금액은?", result))
    finally:
        asyncio.run(provider._http_client.aclose())  # type: ignore[union-attr]


def test_chat_request_timeout_uses_common_provider_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return _completed_response(_intent_payload())

    async def invoke() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAiProvider(
                api_key="test-api-key",
                model="test-model",
                timeout_seconds=0.01,
                http_client=client,
            )
            await provider.classify_intent("남은 금액은?")

    with pytest.raises(AiProviderTimeoutError):
        asyncio.run(invoke())
