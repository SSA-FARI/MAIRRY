from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import ContractStatus, DocumentType
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

    def list_confirmed_matching(
        self,
        wedding_plan_id: UUID,
        *,
        company_terms: tuple[str, ...] = (),
        document_types: tuple[DocumentType, ...] = (),
    ) -> list[Contract]:
        """Return confirmed contracts in one plan, optionally filtered in SQL."""
        filters = []
        if company_terms:
            filters.extend(Contract.company.ilike(f"%{term}%") for term in company_terms)
        if document_types:
            filters.append(Contract.document_type.in_(document_types))
        statement = (
            select(Contract)
            .where(
                Contract.wedding_plan_id == wedding_plan_id,
                Contract.status == ContractStatus.CONFIRMED,
            )
            .options(selectinload(Contract.payments))
            .order_by(Contract.confirmed_at.desc(), Contract.id.desc())
        )
        if filters:
            statement = statement.where(or_(*filters))
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
