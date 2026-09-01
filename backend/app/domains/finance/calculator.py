from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True)
class FinanceCalculationInput:
    assets: tuple[Decimal, ...]
    unpaid_payments: tuple[Decimal, ...]


@dataclass(frozen=True)
class FinanceCalculationResult:
    available_asset: Decimal
    remaining_expense: Decimal
    expected_balance: Decimal


@dataclass(frozen=True)
class SimulationCalculationResult:
    current_expected_balance: Decimal
    simulated_expected_balance: Decimal
    shortage_amount: Decimal


def calculate_finance(payload: FinanceCalculationInput) -> FinanceCalculationResult:
    available_asset = sum(payload.assets, start=ZERO)
    remaining_expense = sum(payload.unpaid_payments, start=ZERO)
    return FinanceCalculationResult(
        available_asset=available_asset,
        remaining_expense=remaining_expense,
        expected_balance=available_asset - remaining_expense,
    )


def calculate_simulation(
    current_expected_balance: Decimal,
    additional_expense: Decimal,
) -> SimulationCalculationResult:
    if additional_expense <= ZERO:
        raise ValueError("additional_expense must be greater than zero")
    simulated_expected_balance = current_expected_balance - additional_expense
    return SimulationCalculationResult(
        current_expected_balance=current_expected_balance,
        simulated_expected_balance=simulated_expected_balance,
        shortage_amount=max(ZERO, -simulated_expected_balance),
    )
