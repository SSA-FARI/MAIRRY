from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.core.enums import PaymentStatus
from app.domains.finance.calculator import (
    FinanceCalculationInput,
    calculate_finance,
    calculate_simulation,
)
from app.domains.finance.schemas import FinancePaymentRecord, PaymentInput
from app.domains.finance.service import (
    FinanceService,
    calculate_summary,
    simulate_additional_expense,
)


def test_fin_01_calculates_assets_and_only_unpaid_payments() -> None:
    summary = calculate_summary(
        30_000_000,
        [
            PaymentInput(amount=3_000_000, status=PaymentStatus.PAID),
            PaymentInput(amount=20_000_000, status=PaymentStatus.UNPAID),
            PaymentInput(amount=5_000_000, status=PaymentStatus.UNKNOWN),
        ],
    )
    assert summary.available_asset == 30_000_000
    assert summary.remaining_expense == 20_000_000
    assert summary.expected_balance == 10_000_000


@pytest.mark.parametrize(
    ("assets", "payments", "expected"),
    [
        ((), (), (Decimal(0), Decimal(0), Decimal(0))),
        ((Decimal(30),), (), (Decimal(30), Decimal(0), Decimal(30))),
        ((Decimal(10), Decimal(20)), (Decimal(30),), (Decimal(30), Decimal(30), Decimal(0))),
        ((Decimal(10),), (Decimal(30),), (Decimal(10), Decimal(30), Decimal(-20))),
        (
            (Decimal(9223372036854775807),),
            (Decimal(9223372036854775806),),
            (Decimal(9223372036854775807), Decimal(9223372036854775806), Decimal(1)),
        ),
    ],
)
def test_finance_calculator_preserves_decimal_precision(
    assets: tuple[Decimal, ...],
    payments: tuple[Decimal, ...],
    expected: tuple[Decimal, Decimal, Decimal],
) -> None:
    result = calculate_finance(FinanceCalculationInput(assets, payments))
    assert (result.available_asset, result.remaining_expense, result.expected_balance) == expected


def test_fin_03_simulates_without_changing_original_summary() -> None:
    summary = calculate_summary(
        30_000_000,
        [PaymentInput(amount=20_000_000, status=PaymentStatus.UNPAID)],
    )
    first = simulate_additional_expense(summary, 3_000_000)
    second = simulate_additional_expense(summary, 3_000_000)
    assert first == second
    assert first.simulated_expected_balance == 7_000_000
    assert first.shortage_amount == 0
    assert summary.expected_balance == 10_000_000


def test_fin_04_reports_shortage() -> None:
    result = calculate_simulation(Decimal(10_000_000), Decimal(15_000_000))
    assert result.simulated_expected_balance == Decimal(-5_000_000)
    assert result.shortage_amount == Decimal(5_000_000)


@pytest.mark.parametrize("amount", [Decimal(0), Decimal(-1)])
def test_simulation_rejects_non_positive_amount(amount: Decimal) -> None:
    with pytest.raises(ValueError):
        calculate_simulation(Decimal(10), amount)


def _payment(payment_id: int, due_date: date | None) -> FinancePaymentRecord:
    return FinancePaymentRecord(
        payment_id=UUID(int=payment_id),
        contract_id=UUID(int=100 + payment_id),
        company=f"업체 {payment_id}",
        name="잔금",
        amount=1_000,
        due_date=due_date,
        created_at=datetime(2026, 1, payment_id, tzinfo=UTC),
    )


def test_timeline_keeps_overdue_and_today_is_eligible_for_nearest() -> None:
    service = FinanceService.__new__(FinanceService)
    service._today = date(2026, 9, 1)
    payments = (
        _payment(1, date(2026, 8, 31)),
        _payment(2, date(2026, 9, 1)),
        _payment(3, date(2026, 9, 2)),
        _payment(4, None),
    )
    summary = service._build_summary((10_000,), payments)
    assert summary.remaining_expense == 4_000
    assert [item.contract_id for item in summary.timeline] == [
        UUID(int=101),
        UUID(int=102),
        UUID(int=103),
    ]
    assert summary.nearest_payment is not None
    assert summary.nearest_payment.contract_id == UUID(int=102)


def test_service_queries_only_current_plan_and_returns_empty_state() -> None:
    plan_id = UUID(int=99)
    service = FinanceService.__new__(FinanceService)
    service._configuration = SimpleNamespace(demo_user_id=UUID(int=1))
    service._today = date(2026, 9, 1)
    service._plans = SimpleNamespace(
        get_current_for_user=lambda user_id: SimpleNamespace(id=plan_id)
    )
    calls: list[UUID] = []
    service._finance = SimpleNamespace(
        asset_amounts=lambda queried_plan_id: calls.append(queried_plan_id) or (),
        confirmed_unpaid_payments=lambda queried_plan_id: calls.append(queried_plan_id) or (),
    )
    summary = service.get_summary()
    assert calls == [plan_id, plan_id]
    assert summary.model_dump(by_alias=True) == {
        "availableAsset": 0,
        "remainingExpense": 0,
        "expectedBalance": 0,
        "nearestPayment": None,
        "timeline": [],
    }
