from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.domains.chat.schemas import ChatResponse, Citation, SimulationCalculation
from app.main import app


class StubChatOrchestrationService:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def process(self, message: str) -> ChatResponse:
        assert message == "웨딩홀 잔금일이 언제야?"
        return ChatResponse(
            answer="A웨딩홀 잔금일은 2027-04-30입니다.",
            answer_type="CONTRACT",
            citations=[
                Citation(
                    contract_id=UUID(int=1),
                    label="A웨딩홀 · 잔금",
                    source_text="잔금은 2027년 4월 30일까지",
                )
            ],
            calculation=None,
        )


def test_chat_response_matches_public_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.domains.chat.router.ChatOrchestrationService",
        StubChatOrchestrationService,
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"message": "웨딩홀 잔금일이 언제야?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "A웨딩홀 잔금일은 2027-04-30입니다.",
        "answerType": "CONTRACT",
        "citations": [
            {
                "contractId": "00000000-0000-0000-0000-000000000001",
                "label": "A웨딩홀 · 잔금",
                "sourceText": "잔금은 2027년 4월 30일까지",
            }
        ],
        "calculation": None,
    }


def test_chat_rejects_blank_extra_and_too_long_messages() -> None:
    client = TestClient(app)

    for payload in (
        {"message": "   "},
        {"message": "질문", "userId": str(UUID(int=2))},
        {"message": "가" * 2_001},
    ):
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_calculation_omits_unrelated_nullable_fields(monkeypatch) -> None:
    class CalculationService(StubChatOrchestrationService):
        def process(self, _message: str) -> ChatResponse:
            return ChatResponse(
                answer="예상 잔액은 7,000,000원입니다.",
                answer_type="CALCULATION",
                citations=[],
                calculation=SimulationCalculation(
                    tool_name="simulateAdditionalExpense",
                    current_expected_balance=10_000_000,
                    simulated_expected_balance=7_000_000,
                    shortage_amount=0,
                    calculated_at=datetime(2026, 9, 3, tzinfo=UTC),
                ),
            )

    monkeypatch.setattr(
        "app.domains.chat.router.ChatOrchestrationService",
        CalculationService,
    )

    payload = TestClient(app).post("/api/chat", json={"message": "가전 300만 원 추가"}).json()

    assert payload["calculation"] == {
        "toolName": "simulateAdditionalExpense",
        "currentExpectedBalance": 10_000_000,
        "simulatedExpectedBalance": 7_000_000,
        "shortageAmount": 0,
        "calculatedAt": "2026-09-03T00:00:00Z",
    }


def test_generated_openapi_chat_shapes_are_typed() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert set(schemas["ChatResponse"]["required"]) == {
        "answer",
        "answerType",
        "citations",
        "calculation",
    }
    assert schemas["ChatResponse"]["properties"]["citations"]["items"] == {
        "$ref": "#/components/schemas/Citation"
    }
