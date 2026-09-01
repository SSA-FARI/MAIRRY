from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient

from app.domains.finance.schemas import FinancePayment, FinanceSummary, SimulationResult
from app.main import app


class StubFinanceService:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def get_summary(self) -> FinanceSummary:
        payment = FinancePayment(
            contract_id=UUID(int=1),
            company="A웨딩홀",
            name="잔금",
            amount=20_000_000,
            due_date=date(2027, 4, 30),
        )
        return FinanceSummary(
            available_asset=30_000_000,
            remaining_expense=20_000_000,
            expected_balance=10_000_000,
            nearest_payment=payment,
            timeline=[payment],
        )

    def simulate(self, additional_amount: int) -> SimulationResult:
        return SimulationResult(
            current_expected_balance=10_000_000,
            simulated_expected_balance=10_000_000 - additional_amount,
            shortage_amount=max(0, additional_amount - 10_000_000),
        )


def test_finance_summary_response_matches_public_contract(monkeypatch) -> None:
    monkeypatch.setattr("app.domains.finance.router.FinanceService", StubFinanceService)
    response = TestClient(app).get("/api/finance/summary")
    assert response.status_code == 200
    assert response.json() == {
        "availableAsset": 30_000_000,
        "remainingExpense": 20_000_000,
        "expectedBalance": 10_000_000,
        "nearestPayment": {
            "contractId": "00000000-0000-0000-0000-000000000001",
            "company": "A웨딩홀",
            "name": "잔금",
            "amount": 20_000_000,
            "dueDate": "2027-04-30",
        },
        "timeline": [
            {
                "contractId": "00000000-0000-0000-0000-000000000001",
                "company": "A웨딩홀",
                "name": "잔금",
                "amount": 20_000_000,
                "dueDate": "2027-04-30",
            }
        ],
    }


def test_simulation_is_not_persisted_and_rejects_invalid_input(monkeypatch) -> None:
    monkeypatch.setattr("app.domains.finance.router.FinanceService", StubFinanceService)
    client = TestClient(app)
    first = client.post("/api/finance/simulate", json={"name": "가전", "amount": 3_000_000})
    second = client.post("/api/finance/simulate", json={"name": "가전", "amount": 3_000_000})
    invalid = client.post("/api/finance/simulate", json={"name": "가전", "amount": 0})
    extra = client.post(
        "/api/finance/simulate",
        json={"name": "가전", "amount": 1, "userId": str(UUID(int=2))},
    )
    assert (
        first.json()
        == second.json()
        == {
            "currentExpectedBalance": 10_000_000,
            "simulatedExpectedBalance": 7_000_000,
            "shortageAmount": 0,
        }
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert extra.status_code == 400


def test_generated_openapi_finance_shapes_match_checked_in_contract() -> None:
    schema = app.openapi()
    summary = schema["components"]["schemas"]["FinanceSummary"]
    simulation = schema["components"]["schemas"]["SimulationResult"]
    assert set(summary["required"]) == {
        "availableAsset",
        "remainingExpense",
        "expectedBalance",
        "nearestPayment",
        "timeline",
    }
    assert set(simulation["required"]) == {
        "currentExpectedBalance",
        "simulatedExpectedBalance",
        "shortageAmount",
    }
