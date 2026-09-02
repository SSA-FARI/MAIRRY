from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.enums import (
    AnalysisSource,
    AssetCategory,
    AssetOwnerType,
    ContractStatus,
    DocumentStatus,
    DocumentType,
    PaymentStatus,
    WeddingPlanMemberRole,
    WeddingPlanStatus,
)
from app.domains.auth.service import DemoLoginService
from app.domains.contracts.models import Contract, Payment
from app.domains.documents.models import Document
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember
from app.domains.wedding_plan.repository import WeddingPlanRepository

DEMO_PLAN_ID = UUID("10000000-0000-0000-0000-000000000001")
DEMO_MEMBER_ID = UUID("10000000-0000-0000-0000-000000000002")
DEMO_ASSET_ID = UUID("10000000-0000-0000-0000-000000000003")
DEMO_HALL_DOCUMENT_ID = UUID("10000000-0000-0000-0000-000000000010")
DEMO_STUDIO_DOCUMENT_ID = UUID("10000000-0000-0000-0000-000000000011")
DEMO_HALL_CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000020")
DEMO_STUDIO_CONTRACT_ID = UUID("10000000-0000-0000-0000-000000000021")
DEMO_HALL_DEPOSIT_ID = UUID("10000000-0000-0000-0000-000000000030")
DEMO_HALL_BALANCE_ID = UUID("10000000-0000-0000-0000-000000000031")
DEMO_STUDIO_DEPOSIT_ID = UUID("10000000-0000-0000-0000-000000000032")
DEMO_STUDIO_BALANCE_ID = UUID("10000000-0000-0000-0000-000000000033")


@dataclass(frozen=True)
class PaymentSeed:
    payment_id: UUID
    contract_id: UUID
    name: str
    amount: int
    due_date: date
    status: PaymentStatus


@dataclass(frozen=True)
class DemoSeedResult:
    wedding_plan_id: UUID
    available_asset: int
    payment_count: int


def payment_seeds(today: date) -> tuple[PaymentSeed, ...]:
    return (
        PaymentSeed(
            DEMO_HALL_DEPOSIT_ID,
            DEMO_HALL_CONTRACT_ID,
            "계약금",
            3_000_000,
            today - timedelta(days=45),
            PaymentStatus.PAID,
        ),
        PaymentSeed(
            DEMO_STUDIO_DEPOSIT_ID,
            DEMO_STUDIO_CONTRACT_ID,
            "중도금",
            3_000_000,
            today + timedelta(days=7),
            PaymentStatus.UNPAID,
        ),
        PaymentSeed(
            DEMO_HALL_BALANCE_ID,
            DEMO_HALL_CONTRACT_ID,
            "잔금",
            20_000_000,
            today + timedelta(days=30),
            PaymentStatus.UNPAID,
        ),
        PaymentSeed(
            DEMO_STUDIO_BALANCE_ID,
            DEMO_STUDIO_CONTRACT_ID,
            "잔금",
            3_000_000,
            today + timedelta(days=90),
            PaymentStatus.UNPAID,
        ),
    )


def seed_demo_data(
    session: Session,
    configuration: Settings,
    *,
    today: date | None = None,
) -> DemoSeedResult:
    seed_date = today or datetime.now(UTC).date()
    DemoLoginService(session, configuration).login()
    plans = WeddingPlanRepository(session)

    try:
        plans.lock_user_plan(configuration.demo_user_id)
        plan = plans.get_current_for_user(configuration.demo_user_id)
        if plan is None:
            plan = WeddingPlan(
                id=DEMO_PLAN_ID,
                wedding_date=seed_date + timedelta(days=240),
                status=WeddingPlanStatus.ACTIVE,
            )
            session.add(plan)
            member = WeddingPlanMember(
                id=DEMO_MEMBER_ID,
                wedding_plan_id=plan.id,
                user_id=configuration.demo_user_id,
                role=WeddingPlanMemberRole.OWNER,
            )
            session.add(member)
            session.flush()
        else:
            plan.wedding_date = seed_date + timedelta(days=240)
            member = session.scalar(
                select(WeddingPlanMember).where(
                    WeddingPlanMember.wedding_plan_id == plan.id,
                    WeddingPlanMember.user_id == configuration.demo_user_id,
                )
            )
            if member is None:
                member = WeddingPlanMember(
                    id=DEMO_MEMBER_ID,
                    wedding_plan_id=plan.id,
                    user_id=configuration.demo_user_id,
                    role=WeddingPlanMemberRole.OWNER,
                )
                session.add(member)
                session.flush()

        asset = plans.get_initial_asset(plan.id)
        if asset is None:
            asset = Asset(
                id=DEMO_ASSET_ID,
                wedding_plan_id=plan.id,
                owner_member_id=None,
                owner_type=AssetOwnerType.JOINT,
                category=AssetCategory.CASH,
                amount=50_000_000,
                label="Demo 공동 자산",
            )
            session.add(asset)
        else:
            asset.amount = 50_000_000
            asset.label = "Demo 공동 자산"

        _upsert_document(session, DEMO_HALL_DOCUMENT_ID, plan.id, member.id, "demo-hall.pdf")
        _upsert_document(
            session,
            DEMO_STUDIO_DOCUMENT_ID,
            plan.id,
            member.id,
            "demo-studio.pdf",
        )
        _upsert_contract(
            session,
            DEMO_HALL_CONTRACT_ID,
            plan.id,
            member.id,
            DEMO_HALL_DOCUMENT_ID,
            DocumentType.WEDDING_HALL,
            "그랜드볼룸 웨딩홀",
            23_000_000,
        )
        _upsert_contract(
            session,
            DEMO_STUDIO_CONTRACT_ID,
            plan.id,
            member.id,
            DEMO_STUDIO_DOCUMENT_ID,
            DocumentType.UNKNOWN,
            "오뜨꾸뛰르 스튜디오",
            6_000_000,
        )
        for payment in payment_seeds(seed_date):
            _upsert_payment(session, payment)

        session.commit()
        return DemoSeedResult(
            wedding_plan_id=plan.id,
            available_asset=50_000_000,
            payment_count=len(payment_seeds(seed_date)),
        )
    except SQLAlchemyError:
        session.rollback()
        raise


def _upsert_document(
    session: Session,
    document_id: UUID,
    wedding_plan_id: UUID,
    member_id: UUID,
    filename: str,
) -> None:
    document = session.get(Document, document_id)
    if document is None:
        document = Document(id=document_id)
        session.add(document)
    document.wedding_plan_id = wedding_plan_id
    document.uploaded_by_member_id = member_id
    document.document_type = DocumentType.WEDDING_HALL.value
    document.original_filename = filename
    document.file_url = f"demo-seed/{filename}"
    document.content_type = "application/pdf"
    document.extraction_raw = None
    document.analysis_status = DocumentStatus.CONFIRMED
    document.analysis_source = AnalysisSource.DEMO_FALLBACK


def _upsert_contract(
    session: Session,
    contract_id: UUID,
    wedding_plan_id: UUID,
    member_id: UUID,
    document_id: UUID,
    document_type: DocumentType,
    company: str,
    total_price: int,
) -> None:
    contract = session.get(Contract, contract_id)
    if contract is None:
        contract = Contract(id=contract_id)
        session.add(contract)
    contract.wedding_plan_id = wedding_plan_id
    contract.document_id = document_id
    contract.document_type = document_type
    contract.company = company
    contract.total_price = total_price
    contract.status = ContractStatus.CONFIRMED
    contract.confirmed_by_member_id = member_id


def _upsert_payment(session: Session, seed: PaymentSeed) -> None:
    payment = session.get(Payment, seed.payment_id)
    if payment is None:
        payment = Payment(id=seed.payment_id)
        session.add(payment)
    payment.contract_id = seed.contract_id
    payment.name = seed.name
    payment.amount = seed.amount
    payment.due_date = seed.due_date
    payment.status = seed.status
    payment.source_text = None


def main() -> None:
    with SessionLocal() as session:
        result = seed_demo_data(session, get_settings())
    print(
        "Demo seed applied "
        f"(wedding_plan_id={result.wedding_plan_id}, "
        f"available_asset={result.available_asset}, payments={result.payment_count})"
    )


if __name__ == "__main__":
    main()
