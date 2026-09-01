from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.finance.calculator import (
    FinanceCalculationInput,
    calculate_finance,
    calculate_simulation,
)
from app.domains.finance.repository import FinanceRepository
from app.domains.finance.schemas import (
    FinancePayment,
    FinancePaymentRecord,
    FinanceSummary,
    PaymentInput,
    SimulationResult,
)
from app.domains.wedding_plan.repository import WeddingPlanRepository


def _integer_amount(value: Decimal) -> int:
    integral = value.to_integral_value()
    if value != integral:
        raise ValueError("finance amounts must be whole won values")
    return int(integral)


def calculate_summary(
    available_asset: int,
    confirmed_payments: Iterable[PaymentInput],
) -> FinanceSummary:
    payments = tuple(confirmed_payments)
    calculated = calculate_finance(
        FinanceCalculationInput(
            assets=(Decimal(available_asset),),
            unpaid_payments=tuple(
                Decimal(payment.amount) for payment in payments if payment.status.value == "UNPAID"
            ),
        )
    )
    return FinanceSummary(
        available_asset=_integer_amount(calculated.available_asset),
        remaining_expense=_integer_amount(calculated.remaining_expense),
        expected_balance=_integer_amount(calculated.expected_balance),
        nearest_payment=None,
        timeline=[],
    )


def simulate_additional_expense(
    summary: FinanceSummary,
    additional_amount: int,
) -> SimulationResult:
    calculated = calculate_simulation(Decimal(summary.expected_balance), Decimal(additional_amount))
    return SimulationResult(
        current_expected_balance=_integer_amount(calculated.current_expected_balance),
        simulated_expected_balance=_integer_amount(calculated.simulated_expected_balance),
        shortage_amount=_integer_amount(calculated.shortage_amount),
    )


class FinanceService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        today: date | None = None,
    ) -> None:
        self._plans = WeddingPlanRepository(session)
        self._finance = FinanceRepository(session)
        self._configuration = configuration
        self._today = today or datetime.now(UTC).date()

    def get_summary(self) -> FinanceSummary:
        try:
            plan = self._plans.get_current_for_user(self._configuration.demo_user_id)
            if plan is None:
                raise AppError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="현재 WeddingPlan이 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            assets = self._finance.asset_amounts(plan.id)
            payments = self._finance.confirmed_unpaid_payments(plan.id)
            return self._build_summary(assets, payments)
        except AppError:
            raise
        except SQLAlchemyError as exc:
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="금융 정보를 조회하지 못했습니다.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

    def simulate(self, additional_amount: int) -> SimulationResult:
        return simulate_additional_expense(self.get_summary(), additional_amount)

    def _build_summary(
        self,
        assets: tuple[int, ...],
        payments: tuple[FinancePaymentRecord, ...],
    ) -> FinanceSummary:
        calculated = calculate_finance(
            FinanceCalculationInput(
                assets=tuple(Decimal(amount) for amount in assets),
                unpaid_payments=tuple(Decimal(payment.amount) for payment in payments),
            )
        )
        dated = tuple(payment for payment in payments if payment.due_date is not None)
        timeline = [self._to_payment(payment) for payment in dated]
        nearest = next(
            (self._to_payment(payment) for payment in dated if payment.due_date >= self._today),
            None,
        )
        return FinanceSummary(
            available_asset=_integer_amount(calculated.available_asset),
            remaining_expense=_integer_amount(calculated.remaining_expense),
            expected_balance=_integer_amount(calculated.expected_balance),
            nearest_payment=nearest,
            timeline=timeline,
        )

    @staticmethod
    def _to_payment(payment: FinancePaymentRecord) -> FinancePayment:
        if payment.due_date is None:
            raise ValueError("timeline payments require due_date")
        return FinancePayment(
            contract_id=payment.contract_id,
            company=payment.company,
            name=payment.name,
            amount=payment.amount,
            due_date=payment.due_date,
        )
