import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.enums import (
    AssetCategory,
    AssetOwnerType,
    ContractStatus,
    DocumentStatus,
    DocumentType,
    PaymentStatus,
    WeddingPlanMemberRole,
)
from app.domains.contracts.models import Contract, Payment
from app.domains.documents.models import Document
from app.domains.users.models import User
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember
from app.main import app

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BASE_DATE = date(2026, 9, 3)


def _test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url is None or not (make_url(database_url).database or "").endswith("_test"):
        pytest.skip("an isolated *_test PostgreSQL database is required")
    return database_url


@pytest.fixture(scope="module")
def database_engine() -> Generator[Engine, None, None]:
    database_url = _test_database_url()
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@dataclass(frozen=True)
class FinanceFixture:
    user_id: uuid.UUID
    other_user_id: uuid.UUID
    plan_id: uuid.UUID
    other_plan_id: uuid.UUID
    member_id: uuid.UUID
    payment_ids: tuple[uuid.UUID, ...]


def _configuration(database_url: str, fixture: FinanceFixture) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        demo_user_id=fixture.user_id,
        demo_wedding_plan_id=fixture.plan_id,
        demo_member_id=fixture.member_id,
        demo_user_login_id=f"finance-{fixture.user_id}",
        demo_user_display_name="Finance Demo",
        demo_user_email=None,
    )


def _new_fixture() -> FinanceFixture:
    return FinanceFixture(
        user_id=uuid.uuid4(),
        other_user_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        other_plan_id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        payment_ids=tuple(uuid.uuid4() for _ in range(4)),
    )


def _add_contract(
    session: Session,
    *,
    plan_id: uuid.UUID,
    member_id: uuid.UUID,
    company: str,
    payments: list[tuple[uuid.UUID, str, int, date, PaymentStatus]],
) -> None:
    document = Document(
        id=uuid.uuid4(),
        wedding_plan_id=plan_id,
        uploaded_by_member_id=member_id,
        original_filename="finance-fixture.pdf",
        file_url=f"test-fixtures/{uuid.uuid4()}.pdf",
        content_type="application/pdf",
        analysis_status=DocumentStatus.CONFIRMED,
    )
    session.add(document)
    session.flush()

    contract = Contract(
        id=uuid.uuid4(),
        wedding_plan_id=plan_id,
        document_id=document.id,
        document_type=DocumentType.WEDDING_HALL,
        company=company,
        total_price=sum(amount for _id, _name, amount, _due_date, _status in payments),
        status=ContractStatus.CONFIRMED,
        confirmed_by_member_id=member_id,
    )
    session.add(contract)
    session.flush()
    session.add_all(
        [
            Payment(
                id=payment_id,
                contract_id=contract.id,
                name=name,
                amount=amount,
                due_date=due_date,
                status=payment_status,
            )
            for payment_id, name, amount, due_date, payment_status in payments
        ]
    )


def _seed_finance_fixture(engine: Engine, fixture: FinanceFixture) -> None:
    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=fixture.user_id,
                    login_id=f"finance-{fixture.user_id}",
                    password_hash="fixture-only",
                    display_name="Finance A",
                ),
                User(
                    id=fixture.other_user_id,
                    login_id=f"finance-other-{fixture.other_user_id}",
                    password_hash="fixture-only",
                    display_name="Finance B",
                ),
                WeddingPlan(id=fixture.plan_id, wedding_date=date(2027, 5, 15)),
                WeddingPlan(id=fixture.other_plan_id, wedding_date=date(2027, 6, 15)),
            ]
        )
        session.flush()
        other_member_id = uuid.uuid4()
        session.add_all(
            [
                WeddingPlanMember(
                    id=fixture.member_id,
                    wedding_plan_id=fixture.plan_id,
                    user_id=fixture.user_id,
                    role=WeddingPlanMemberRole.OWNER,
                ),
                WeddingPlanMember(
                    id=other_member_id,
                    wedding_plan_id=fixture.other_plan_id,
                    user_id=fixture.other_user_id,
                    role=WeddingPlanMemberRole.OWNER,
                ),
                Asset(
                    id=uuid.uuid4(),
                    wedding_plan_id=fixture.plan_id,
                    owner_member_id=None,
                    owner_type=AssetOwnerType.JOINT,
                    category=AssetCategory.CASH,
                    amount=50_000_000,
                ),
                Asset(
                    id=uuid.uuid4(),
                    wedding_plan_id=fixture.other_plan_id,
                    owner_member_id=None,
                    owner_type=AssetOwnerType.JOINT,
                    category=AssetCategory.CASH,
                    amount=100_000_000,
                ),
            ]
        )
        session.flush()
        _add_contract(
            session,
            plan_id=fixture.plan_id,
            member_id=fixture.member_id,
            company="그랜드볼룸 웨딩홀",
            payments=[
                (
                    fixture.payment_ids[0],
                    "계약금",
                    5_000_000,
                    BASE_DATE - timedelta(days=30),
                    PaymentStatus.PAID,
                ),
                (
                    fixture.payment_ids[1],
                    "중도금",
                    10_000_000,
                    BASE_DATE - timedelta(days=2),
                    PaymentStatus.UNPAID,
                ),
                (
                    fixture.payment_ids[2],
                    "잔금",
                    15_000_000,
                    BASE_DATE + timedelta(days=20),
                    PaymentStatus.UNPAID,
                ),
            ],
        )
        _add_contract(
            session,
            plan_id=fixture.plan_id,
            member_id=fixture.member_id,
            company="오뜨꾸뛰르 스튜디오",
            payments=[
                (
                    fixture.payment_ids[3],
                    "잔금",
                    3_000_000,
                    BASE_DATE + timedelta(days=4),
                    PaymentStatus.UNPAID,
                )
            ],
        )
        _add_contract(
            session,
            plan_id=fixture.other_plan_id,
            member_id=other_member_id,
            company="다른 Plan 업체",
            payments=[
                (
                    uuid.uuid4(),
                    "잔금",
                    40_000_000,
                    BASE_DATE + timedelta(days=1),
                    PaymentStatus.UNPAID,
                )
            ],
        )
        session.commit()


def _cleanup(engine: Engine, fixture: FinanceFixture) -> None:
    with Session(engine) as session:
        plan_ids = (fixture.plan_id, fixture.other_plan_id)
        contract_ids = session.scalars(
            select(Contract.id).where(Contract.wedding_plan_id.in_(plan_ids))
        ).all()
        document_ids = session.scalars(
            select(Document.id).where(Document.wedding_plan_id.in_(plan_ids))
        ).all()
        if contract_ids:
            session.execute(Payment.__table__.delete().where(Payment.contract_id.in_(contract_ids)))
            session.execute(Contract.__table__.delete().where(Contract.id.in_(contract_ids)))
        if document_ids:
            session.execute(Document.__table__.delete().where(Document.id.in_(document_ids)))
        session.execute(Asset.__table__.delete().where(Asset.wedding_plan_id.in_(plan_ids)))
        session.execute(
            WeddingPlanMember.__table__.delete().where(
                WeddingPlanMember.wedding_plan_id.in_(plan_ids)
            )
        )
        session.execute(WeddingPlan.__table__.delete().where(WeddingPlan.id.in_(plan_ids)))
        session.execute(
            User.__table__.delete().where(User.id.in_((fixture.user_id, fixture.other_user_id)))
        )
        session.commit()


@pytest.fixture
def finance_scope(
    database_engine: Engine,
) -> Generator[tuple[TestClient, FinanceFixture], None, None]:
    fixture = _new_fixture()
    configuration = _configuration(str(database_engine.url), fixture)
    _seed_finance_fixture(database_engine, fixture)

    def database_session() -> Generator[Session, None, None]:
        with Session(database_engine) as session:
            yield session

    app.dependency_overrides[get_db] = database_session
    app.dependency_overrides[get_settings] = lambda: configuration
    try:
        yield TestClient(app), fixture
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, fixture)


def test_fin_01_to_03_summary_nearest_timeline_and_plan_isolation(
    finance_scope: tuple[TestClient, FinanceFixture],
) -> None:
    client, _fixture = finance_scope

    response = client.get("/api/finance/summary")

    assert response.status_code == 200
    assert response.json() == {
        "availableAsset": 50_000_000,
        "remainingExpense": 28_000_000,
        "expectedBalance": 22_000_000,
        "nearestPayment": {
            "contractId": response.json()["nearestPayment"]["contractId"],
            "company": "오뜨꾸뛰르 스튜디오",
            "name": "잔금",
            "amount": 3_000_000,
            "dueDate": "2026-09-07",
        },
        "timeline": [
            {
                "contractId": response.json()["timeline"][0]["contractId"],
                "company": "그랜드볼룸 웨딩홀",
                "name": "중도금",
                "amount": 10_000_000,
                "dueDate": "2026-09-01",
            },
            {
                "contractId": response.json()["timeline"][1]["contractId"],
                "company": "오뜨꾸뛰르 스튜디오",
                "name": "잔금",
                "amount": 3_000_000,
                "dueDate": "2026-09-07",
            },
            {
                "contractId": response.json()["timeline"][2]["contractId"],
                "company": "그랜드볼룸 웨딩홀",
                "name": "잔금",
                "amount": 15_000_000,
                "dueDate": "2026-09-23",
            },
        ],
    }


def test_finance_reloads_payment_status_and_new_rows_from_database(
    database_engine: Engine,
    finance_scope: tuple[TestClient, FinanceFixture],
) -> None:
    client, fixture = finance_scope
    before = client.get("/api/finance/summary").json()

    with Session(database_engine) as session:
        payment = session.get(Payment, fixture.payment_ids[1])
        assert payment is not None
        payment.status = PaymentStatus.PAID
        _add_contract(
            session,
            plan_id=fixture.plan_id,
            member_id=fixture.member_id,
            company="청첩장 인쇄소",
            payments=[
                (
                    uuid.uuid4(),
                    "잔금",
                    500_000,
                    BASE_DATE + timedelta(days=10),
                    PaymentStatus.UNPAID,
                )
            ],
        )
        session.commit()

    after = client.get("/api/finance/summary").json()

    assert (before["remainingExpense"], before["expectedBalance"]) == (
        28_000_000,
        22_000_000,
    )
    assert (after["remainingExpense"], after["expectedBalance"]) == (
        18_500_000,
        31_500_000,
    )
    assert all(item["name"] != "중도금" for item in after["timeline"])
    assert any(item["company"] == "청첩장 인쇄소" for item in after["timeline"])


def test_fin_04_simulation_is_not_persisted(
    database_engine: Engine,
    finance_scope: tuple[TestClient, FinanceFixture],
) -> None:
    client, fixture = finance_scope
    with Session(database_engine) as session:
        before_counts = (
            session.scalar(select(func.count()).select_from(Asset)),
            session.scalar(select(func.count()).select_from(Contract)),
            session.scalar(select(func.count()).select_from(Payment)),
        )

    first = client.post("/api/finance/simulate", json={"name": "가전 비용", "amount": 30_000_000})
    second = client.post("/api/finance/simulate", json={"name": "가전 비용", "amount": 30_000_000})
    invalid = client.post(
        "/api/finance/simulate",
        json={"name": "가전 비용", "amount": 0, "userId": str(fixture.other_user_id)},
    )

    assert first.status_code == 200
    assert (
        first.json()
        == second.json()
        == {
            "currentExpectedBalance": 22_000_000,
            "simulatedExpectedBalance": -8_000_000,
            "shortageAmount": 8_000_000,
        }
    )
    assert invalid.status_code == 400
    with Session(database_engine) as session:
        after_counts = (
            session.scalar(select(func.count()).select_from(Asset)),
            session.scalar(select(func.count()).select_from(Contract)),
            session.scalar(select(func.count()).select_from(Payment)),
        )
    assert after_counts == before_counts
