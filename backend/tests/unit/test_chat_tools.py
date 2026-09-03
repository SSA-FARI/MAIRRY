from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.enums import ContractStatus, DocumentType, PaymentStatus
from app.domains.chat.tools import ChatToolRegistry
from app.domains.contracts.models import CancellationTerm, Contract, Payment
from app.domains.finance.schemas import FinanceSummary, SimulationResult

NOW = datetime(2026, 9, 3, 1, 2, 3, tzinfo=UTC)
USER_ID = UUID(int=1)
PLAN_ID = UUID(int=2)
CONTRACT_ID = UUID(int=3)


def _payment(
    payment_id: int,
    *,
    due_date: date | None,
    status: PaymentStatus = PaymentStatus.UNPAID,
    source_text: str | None = "잔금 근거",
) -> Payment:
    return Payment(
        id=UUID(int=payment_id),
        name="잔금",
        amount=20_000_000,
        due_date=due_date,
        status=status,
        source_text=source_text,
        created_at=NOW,
    )


def _contract(*payments: Payment) -> Contract:
    return Contract(
        id=CONTRACT_ID,
        wedding_plan_id=PLAN_ID,
        document_id=UUID(int=4),
        document_type=DocumentType.WEDDING_HALL,
        company="A웨딩홀",
        total_price=23_000_000,
        status=ContractStatus.CONFIRMED,
        confirmed_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        payments=list(payments),
        cancellation_terms=[
            CancellationTerm(
                id=UUID(int=10),
                summary="예식 90일 전까지 계약금 환급",
                source_text="90일 전까지 전액 환급",
                created_at=NOW,
                updated_at=NOW,
            )
        ],
    )


def _registry() -> ChatToolRegistry:
    registry = ChatToolRegistry.__new__(ChatToolRegistry)
    registry._configuration = SimpleNamespace(demo_user_id=USER_ID)
    registry._now_provider = lambda: NOW
    registry._today_provider = lambda: date(2026, 9, 3)
    registry._plans = SimpleNamespace(
        get_current_for_user=lambda user_id: SimpleNamespace(id=PLAN_ID)
    )
    registry._contracts = SimpleNamespace()
    registry._finance = SimpleNamespace()
    return registry


def test_chat_01_contract_tool_returns_owned_data_and_source_evidence() -> None:
    registry = _registry()
    contract = _contract(_payment(5, due_date=date(2027, 4, 30)))
    queried: list[tuple[UUID, UUID]] = []
    registry._contracts.get_confirmed = lambda plan_id, contract_id: (
        queried.append((plan_id, contract_id)) or contract
    )

    result = registry.execute(
        "getContractDetails",
        {"contractId": str(CONTRACT_ID)},
        USER_ID,
    )

    assert queried == [(PLAN_ID, CONTRACT_ID)]
    assert result.status == "SUCCESS"
    assert result.data is not None
    assert result.data["company"] == "A웨딩홀"
    assert result.evidence == [
        {
            "contractId": str(CONTRACT_ID),
            "label": "A웨딩홀 · 잔금",
            "sourceText": "잔금 근거",
        },
        {
            "contractId": str(CONTRACT_ID),
            "label": "A웨딩홀 · 취소조건",
            "sourceText": "90일 전까지 전액 환급",
        },
    ]


def test_chat_04_upcoming_tool_filters_unpaid_dates_and_applies_limit() -> None:
    registry = _registry()
    registry._contracts.list_confirmed = lambda _plan_id: [
        _contract(
            _payment(5, due_date=date(2026, 9, 2)),
            _payment(6, due_date=date(2027, 4, 30)),
            _payment(7, due_date=date(2027, 1, 1), status=PaymentStatus.PAID),
            _payment(8, due_date=date(2027, 3, 1)),
        )
    ]

    result = registry.execute("getUpcomingPayments", {"limit": 1}, USER_ID)

    assert result.status == "SUCCESS"
    assert result.data is not None
    assert result.data["payments"] == [
        {
            "contractId": str(CONTRACT_ID),
            "company": "A웨딩홀",
            "name": "잔금",
            "amount": 20_000_000,
            "dueDate": "2027-03-01",
            "status": "UNPAID",
        }
    ]


def test_chat_05_finance_tool_reuses_server_calculation() -> None:
    registry = _registry()
    registry._finance.get_summary = lambda **_kwargs: FinanceSummary(
        available_asset=30_000_000,
        remaining_expense=20_000_000,
        expected_balance=10_000_000,
        nearest_payment=None,
        timeline=[],
    )

    result = registry.execute("getFinanceSummary", {}, USER_ID)

    assert result.status == "SUCCESS"
    assert result.data is not None
    assert result.data["expectedBalance"] == 10_000_000
    assert result.calculated_at == NOW


def test_chat_06_10_simulation_is_forwarded_and_deterministic() -> None:
    registry = _registry()
    calls: list[tuple[int, UUID]] = []

    def simulate(amount: int, *, user_id: UUID) -> SimulationResult:
        calls.append((amount, user_id))
        return SimulationResult(
            current_expected_balance=10_000_000,
            simulated_expected_balance=7_000_000,
            shortage_amount=0,
        )

    registry._finance.simulate = simulate
    arguments = {"name": "가전 비용", "amount": 3_000_000}
    first = registry.execute("simulateAdditionalExpense", arguments, USER_ID)
    second = registry.execute("simulateAdditionalExpense", arguments, USER_ID)

    assert first == second
    assert calls == [(3_000_000, USER_ID), (3_000_000, USER_ID)]
    assert first.data is not None
    assert first.data["simulatedExpectedBalance"] == 7_000_000


def test_chat_03_08_09_failures_never_include_data_or_evidence() -> None:
    registry = _registry()
    registry._contracts.get_confirmed = lambda _plan_id, _contract_id: None
    not_found = registry.execute(
        "getContractDetails",
        {"contractId": str(CONTRACT_ID)},
        USER_ID,
    )

    registry._finance.get_summary = lambda **_kwargs: (_ for _ in ()).throw(
        SQLAlchemyError("database unavailable")
    )
    tool_error = registry.execute("getFinanceSummary", {}, USER_ID)
    invalid = registry.execute("simulateAdditionalExpense", {"name": "가전"}, USER_ID)

    assert [not_found.status, invalid.status, tool_error.status] == [
        "NOT_FOUND",
        "INVALID_ARGUMENT",
        "TOOL_ERROR",
    ]
    for result in (not_found, invalid, tool_error):
        assert result.data is None
        assert result.evidence == []
