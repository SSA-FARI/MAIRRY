from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ContractStatus, PaymentStatus
from app.domains.contracts.models import Contract, Payment
from app.domains.finance.schemas import FinancePaymentRecord
from app.domains.wedding_plan.models import Asset


class FinanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def asset_amounts(self, wedding_plan_id: UUID) -> tuple[int, ...]:
        statement = (
            select(Asset.amount)
            .where(Asset.wedding_plan_id == wedding_plan_id)
            .order_by(Asset.created_at, Asset.id)
        )
        return tuple(self._session.scalars(statement))

    def confirmed_unpaid_payments(self, wedding_plan_id: UUID) -> tuple[FinancePaymentRecord, ...]:
        statement = (
            select(
                Payment.id,
                Payment.contract_id,
                Contract.company,
                Payment.name,
                Payment.amount,
                Payment.due_date,
                Payment.created_at,
            )
            .join(Contract, Contract.id == Payment.contract_id)
            .where(
                Contract.wedding_plan_id == wedding_plan_id,
                Contract.status == ContractStatus.CONFIRMED,
                Payment.status == PaymentStatus.UNPAID,
            )
            .order_by(Payment.due_date.asc().nulls_last(), Payment.created_at, Payment.id)
        )
        return tuple(
            FinancePaymentRecord(
                payment_id=row.id,
                contract_id=row.contract_id,
                company=row.company,
                name=row.name,
                amount=row.amount,
                due_date=row.due_date,
                created_at=row.created_at,
            )
            for row in self._session.execute(statement)
        )
