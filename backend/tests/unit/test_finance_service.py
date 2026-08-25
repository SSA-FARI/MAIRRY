from app.domains.finance.schemas import PaymentInput
from app.domains.finance.service import (
    calculate_summary,
    simulate_additional_expense,
)


def test_calculate_summary_uses_only_unpaid_payments() -> None:
    payments = [
        PaymentInput(amount=3_000_000, status="PAID"),
        PaymentInput(amount=20_000_000, status="UNPAID"),
    ]

    summary = calculate_summary(30_000_000, payments)

    assert summary.remaining_expense == 20_000_000
    assert summary.expected_balance == 10_000_000


def test_simulate_additional_expense() -> None:
    summary = calculate_summary(
        30_000_000,
        [PaymentInput(amount=20_000_000, status="UNPAID")],
    )

    result = simulate_additional_expense(summary, 3_000_000)

    assert result.simulated_expected_balance == 7_000_000
    assert result.shortage_amount == 0

