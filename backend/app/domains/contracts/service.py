from collections.abc import Callable
from datetime import date
from uuid import UUID

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import PaymentStatus
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.contracts.models import CancellationTerm, Contract, Payment
from app.domains.contracts.repository import ContractRepository
from app.domains.contracts.schemas import (
    ConfirmedCancellationTermRead,
    ConfirmedPaymentRead,
    ContractDetailRead,
    ContractListRead,
    ContractSummaryRead,
    UpcomingPaymentRead,
)
from app.domains.wedding_plan.repository import WeddingPlanRepository

TodayProvider = Callable[[], date]


class ContractQueryService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        today_provider: TodayProvider = date.today,
    ) -> None:
        self._session = session
        self._configuration = configuration
        self._today_provider = today_provider
        self._contracts = ContractRepository(session)
        self._plans = WeddingPlanRepository(session)

    def list_contracts(self) -> ContractListRead:
        try:
            plan = self._plans.get_current_for_user(self._configuration.demo_user_id)
            if plan is None:
                return ContractListRead(items=[])
            contracts = self._contracts.list_confirmed(plan.id)
            return ContractListRead(items=[self._to_summary(contract) for contract in contracts])
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise self._internal_error("계약 목록을 조회하지 못했습니다.") from exc

    def get_contract(self, contract_id: UUID) -> ContractDetailRead:
        try:
            plan = self._plans.get_current_for_user(self._configuration.demo_user_id)
            contract = (
                self._contracts.get_confirmed(plan.id, contract_id) if plan is not None else None
            )
            if contract is None:
                raise AppError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="요청한 계약을 찾을 수 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return self._to_detail(contract)
        except AppError:
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise self._internal_error("계약 상세를 조회하지 못했습니다.") from exc

    def _to_summary(self, contract: Contract) -> ContractSummaryRead:
        return ContractSummaryRead(
            id=contract.id,
            company=contract.company,
            total_price=contract.total_price,
            status=contract.status,
            next_payment=self._next_payment(contract),
        )

    def _next_payment(self, contract: Contract) -> UpcomingPaymentRead | None:
        today = self._today_provider()
        candidates = [
            payment
            for payment in contract.payments
            if payment.status == PaymentStatus.UNPAID
            and payment.due_date is not None
            and payment.due_date >= today
        ]
        if not candidates:
            return None
        payment = min(candidates, key=lambda item: (item.due_date, item.id))
        assert payment.due_date is not None
        return UpcomingPaymentRead(
            contract_id=contract.id,
            company=contract.company,
            name=payment.name,
            amount=payment.amount,
            due_date=payment.due_date,
        )

    def _to_detail(self, contract: Contract) -> ContractDetailRead:
        payments = sorted(
            contract.payments,
            key=lambda item: (item.due_date is None, item.due_date or date.max, item.id),
        )
        cancellation_terms = sorted(
            contract.cancellation_terms,
            key=lambda item: (item.created_at, item.id),
        )
        return ContractDetailRead(
            id=contract.id,
            document_id=contract.document_id,
            document_type=contract.document_type,
            company=contract.company,
            total_price=contract.total_price,
            status=contract.status,
            payments=[self._to_payment(payment) for payment in payments],
            cancellation_terms=[self._to_cancellation_term(term) for term in cancellation_terms],
        )

    @staticmethod
    def _to_payment(payment: Payment) -> ConfirmedPaymentRead:
        return ConfirmedPaymentRead(
            name=payment.name,
            amount=payment.amount,
            due_date=payment.due_date,
            status=payment.status,
            source_text=payment.source_text,
        )

    @staticmethod
    def _to_cancellation_term(
        term: CancellationTerm,
    ) -> ConfirmedCancellationTermRead:
        return ConfirmedCancellationTermRead(
            summary=term.summary,
            source_text=term.source_text,
        )

    @staticmethod
    def _internal_error(message: str) -> AppError:
        return AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
