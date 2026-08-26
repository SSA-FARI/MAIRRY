from collections.abc import Iterable

from app.domains.finance.schemas import (
    FinanceSummary,
    PaymentInput,
    SimulationResult,
)


def calculate_summary(
    available_asset: int,
    confirmed_payments: Iterable[PaymentInput],
) -> FinanceSummary:
    remaining_expense = sum(
        payment.amount for payment in confirmed_payments if payment.status == "UNPAID"
    )
    return FinanceSummary(
        available_asset=available_asset,
        remaining_expense=remaining_expense,
        expected_balance=available_asset - remaining_expense,
    )


def simulate_additional_expense(
    summary: FinanceSummary,
    additional_amount: int,
) -> SimulationResult:
    simulated_balance = summary.expected_balance - additional_amount
    return SimulationResult(
        current_expected_balance=summary.expected_balance,
        simulated_expected_balance=simulated_balance,
        shortage_amount=max(0, -simulated_balance),
    )
