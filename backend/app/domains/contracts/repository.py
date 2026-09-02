from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import ContractStatus
from app.domains.contracts.models import Contract


class ContractRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_confirmed(self, wedding_plan_id: UUID) -> list[Contract]:
        statement = (
            select(Contract)
            .where(
                Contract.wedding_plan_id == wedding_plan_id,
                Contract.status == ContractStatus.CONFIRMED,
            )
            .options(selectinload(Contract.payments))
            .order_by(Contract.confirmed_at.desc(), Contract.id.desc())
        )
        return list(self._session.scalars(statement).all())

    def get_confirmed(
        self,
        wedding_plan_id: UUID,
        contract_id: UUID,
        *,
        for_update: bool = False,
    ) -> Contract | None:
        statement = (
            select(Contract)
            .where(
                Contract.id == contract_id,
                Contract.wedding_plan_id == wedding_plan_id,
                Contract.status == ContractStatus.CONFIRMED,
            )
            .options(
                selectinload(Contract.payments),
                selectinload(Contract.cancellation_terms),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add(self, contract: Contract) -> None:
        self._session.add(contract)

    def delete(self, contract: Contract) -> None:
        self._session.delete(contract)
