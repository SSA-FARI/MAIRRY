from collections.abc import Callable
from datetime import date
from uuid import UUID

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ContractStatus, DocumentStatus, PaymentStatus
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.contracts.models import CancellationTerm, Contract, Payment
from app.domains.contracts.repository import ContractRepository
from app.domains.contracts.schemas import (
    ConfirmedCancellationTermRead,
    ConfirmedPaymentRead,
    ContractConfirm,
    ContractDetailRead,
    ContractListRead,
    ContractSummaryRead,
    UpcomingPaymentRead,
)
from app.domains.documents.models import Document
from app.domains.documents.repository import DocumentRepository
from app.domains.wedding_plan.repository import WeddingPlanRepository

TodayProvider = Callable[[], date]


def build_payments(payload: ContractConfirm, *, preserve_evidence: bool) -> list[Payment]:
    return [
        Payment(
            name=payment.name,
            amount=payment.amount,
            due_date=payment.due_date,
            status=payment.status,
            source_text=payment.source_text if preserve_evidence else None,
        )
        for payment in payload.payments
    ]


def build_cancellation_terms(
    payload: ContractConfirm,
    *,
    preserve_evidence: bool,
) -> list[CancellationTerm]:
    return [
        CancellationTerm(
            summary=term.summary,
            source_text=term.source_text if preserve_evidence else None,
        )
        for term in payload.cancellation_terms
    ]


def build_contract_detail(contract: Contract) -> ContractDetailRead:
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
        payments=[
            ConfirmedPaymentRead(
                name=payment.name,
                amount=payment.amount,
                due_date=payment.due_date,
                status=payment.status,
                source_text=payment.source_text,
            )
            for payment in payments
        ],
        cancellation_terms=[
            ConfirmedCancellationTermRead(
                summary=term.summary,
                source_text=term.source_text,
            )
            for term in cancellation_terms
        ],
    )


class ContractConfirmationService:
    def __init__(self, session: Session, configuration: Settings) -> None:
        self._session = session
        self._configuration = configuration
        self._contracts = ContractRepository(session)
        self._documents = DocumentRepository()
        self._plans = WeddingPlanRepository(session)

    def confirm(self, document_id: UUID, payload: ContractConfirm) -> ContractDetailRead:
        try:
            user_id = self._configuration.demo_user_id
            plan = self._plans.get_current_for_user(user_id)
            if plan is None:
                raise self._not_found()
            member = self._plans.get_member_for_user(plan.id, user_id)
            if member is None:
                raise self._not_found()

            document = self._documents.get_by_id(
                self._session,
                document_id,
                plan.id,
                for_update=True,
            )
            if document is None:
                raise self._not_found()
            if document.analysis_status not in {
                DocumentStatus.REVIEW_REQUIRED,
                DocumentStatus.FAILED,
            }:
                raise AppError(
                    code=ErrorCode.INVALID_STATE,
                    message="검수 대기 또는 직접 입력 상태의 문서만 확정할 수 있습니다.",
                    status_code=status.HTTP_409_CONFLICT,
                )

            preserve_evidence = document.analysis_status == DocumentStatus.REVIEW_REQUIRED
            contract = Contract(
                wedding_plan_id=plan.id,
                document_id=document.id,
                document_type=payload.document_type,
                company=payload.company,
                total_price=payload.total_price,
                status=ContractStatus.CONFIRMED,
                confirmed_by_member_id=member.id,
                payments=build_payments(payload, preserve_evidence=preserve_evidence),
                cancellation_terms=build_cancellation_terms(
                    payload,
                    preserve_evidence=preserve_evidence,
                ),
            )
            document.document_type = payload.document_type.value
            document.analysis_status = DocumentStatus.CONFIRMED
            self._contracts.add(contract)
            self._session.flush()
            response = build_contract_detail(contract)
            self._session.commit()
            return response
        except AppError:
            self._session.rollback()
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise ContractQueryService._internal_error("계약을 확정하지 못했습니다.") from exc
        except Exception:
            self._session.rollback()
            raise

    @staticmethod
    def _not_found() -> AppError:
        return AppError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="확정할 문서 또는 웨딩 계획을 찾을 수 없습니다.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ContractManagementService:
    def __init__(self, session: Session, configuration: Settings) -> None:
        self._session = session
        self._configuration = configuration
        self._contracts = ContractRepository(session)
        self._documents = DocumentRepository()
        self._plans = WeddingPlanRepository(session)

    def update(self, contract_id: UUID, payload: ContractConfirm) -> ContractDetailRead:
        try:
            contract = self._get_contract(contract_id)
            document = self._get_document(contract)
            contract.document_type = payload.document_type
            document.document_type = payload.document_type.value
            contract.company = payload.company
            contract.total_price = payload.total_price
            contract.payments = build_payments(payload, preserve_evidence=True)
            contract.cancellation_terms = build_cancellation_terms(
                payload,
                preserve_evidence=True,
            )
            self._session.flush()
            response = build_contract_detail(contract)
            self._session.commit()
            return response
        except AppError:
            self._session.rollback()
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise ContractQueryService._internal_error("계약을 수정하지 못했습니다.") from exc

    def delete(self, contract_id: UUID) -> None:
        try:
            contract = self._get_contract(contract_id)
            document = self._get_document(contract)
            document.analysis_status = (
                DocumentStatus.REVIEW_REQUIRED
                if document.extraction_raw is not None
                else DocumentStatus.FAILED
            )
            self._contracts.delete(contract)
            self._session.flush()
            self._session.commit()
        except AppError:
            self._session.rollback()
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise ContractQueryService._internal_error("계약을 삭제하지 못했습니다.") from exc

    def _get_contract(self, contract_id: UUID) -> Contract:
        plan = self._plans.get_current_for_user(self._configuration.demo_user_id)
        contract = (
            self._contracts.get_confirmed(plan.id, contract_id, for_update=True)
            if plan is not None
            else None
        )
        if contract is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="요청한 계약을 찾을 수 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return contract

    def _get_document(self, contract: Contract) -> Document:
        document = self._documents.get_by_id(
            self._session,
            contract.document_id,
            contract.wedding_plan_id,
            for_update=True,
        )
        if document is None:
            raise ContractConfirmationService._not_found()
        return document


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
            return build_contract_detail(contract)
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

    @staticmethod
    def _internal_error(message: str) -> AppError:
        return AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
