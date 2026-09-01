import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.enums import (
    ContractStatus,
    DocumentStatus,
    DocumentType,
    PaymentStatus,
    WeddingPlanMemberRole,
)
from app.domains.contracts.models import CancellationTerm, Contract, Payment
from app.domains.documents.models import Document
from app.domains.users.models import User
from app.domains.wedding_plan.models import WeddingPlan, WeddingPlanMember
from app.main import app

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


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


def _configuration(database_url: str, user_id: uuid.UUID) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        demo_user_id=user_id,
        demo_user_login_id=f"contract-{user_id}",
        demo_user_display_name="Contract Demo",
        demo_user_email=None,
    )


def _override_dependencies(engine: Engine, configuration: Settings) -> None:
    def database_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database_session
    app.dependency_overrides[get_settings] = lambda: configuration


def _create_user_plan(session: Session, user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    plan_id = uuid.uuid4()
    member_id = uuid.uuid4()
    session.add(
        User(
            id=user_id,
            login_id=f"contract-{user_id}",
            password_hash="$2b$12$not-a-login-credential",
            display_name="Contract Demo",
        )
    )
    session.add(WeddingPlan(id=plan_id, wedding_date=date(2099, 5, 15)))
    session.add(
        WeddingPlanMember(
            id=member_id,
            wedding_plan_id=plan_id,
            user_id=user_id,
            role=WeddingPlanMemberRole.OWNER,
        )
    )
    return plan_id, member_id


def _create_contract(
    session: Session,
    *,
    plan_id: uuid.UUID,
    member_id: uuid.UUID,
    company: str,
    confirmed_at: datetime,
    payments: list[tuple[str, int, date | None, PaymentStatus, str | None]],
) -> Contract:
    document = Document(
        id=uuid.uuid4(),
        wedding_plan_id=plan_id,
        uploaded_by_member_id=member_id,
        original_filename=f"{company}.pdf",
        file_url=f"documents/{uuid.uuid4()}.pdf",
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
        total_price=sum(amount for _name, amount, _due, _status, _source in payments),
        status=ContractStatus.CONFIRMED,
        confirmed_by_member_id=member_id,
        confirmed_at=confirmed_at,
    )
    contract.payments = [
        Payment(
            id=uuid.uuid4(),
            name=name,
            amount=amount,
            due_date=due_date,
            status=payment_status,
            source_text=source_text,
        )
        for name, amount, due_date, payment_status, source_text in payments
    ]
    contract.cancellation_terms = [
        CancellationTerm(
            id=uuid.uuid4(),
            summary="예식 90일 전까지 계약금 환급",
            source_text=None,
        )
    ]
    session.add(contract)
    return contract


def _cleanup(engine: Engine, user_ids: list[uuid.UUID]) -> None:
    with Session(engine) as session:
        plan_ids = [
            plan_id
            for user_id in user_ids
            for plan_id in session.scalars(
                select(WeddingPlanMember.wedding_plan_id).where(
                    WeddingPlanMember.user_id == user_id
                )
            ).all()
        ]
        if plan_ids:
            contract_ids = session.query(Contract.id).filter(Contract.wedding_plan_id.in_(plan_ids))
            session.query(CancellationTerm).filter(
                CancellationTerm.contract_id.in_(contract_ids)
            ).delete(synchronize_session=False)
            session.query(Payment).filter(Payment.contract_id.in_(contract_ids)).delete(
                synchronize_session=False
            )
            session.query(Contract).filter(Contract.wedding_plan_id.in_(plan_ids)).delete(
                synchronize_session=False
            )
            session.query(Document).filter(Document.wedding_plan_id.in_(plan_ids)).delete(
                synchronize_session=False
            )
            session.query(WeddingPlanMember).filter(
                WeddingPlanMember.wedding_plan_id.in_(plan_ids)
            ).delete(synchronize_session=False)
            session.query(WeddingPlan).filter(WeddingPlan.id.in_(plan_ids)).delete(
                synchronize_session=False
            )
        session.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        session.commit()


def test_contract_list_returns_recent_confirmed_contracts_and_next_payment(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id, other_user_id])
    with Session(database_engine) as session:
        plan_id, member_id = _create_user_plan(session, user_id)
        other_plan_id, other_member_id = _create_user_plan(session, other_user_id)
        older = _create_contract(
            session,
            plan_id=plan_id,
            member_id=member_id,
            company="A웨딩홀",
            confirmed_at=datetime(2026, 8, 1, tzinfo=UTC),
            payments=[("잔금", 20_000_000, date(2099, 4, 30), PaymentStatus.UNPAID, "잔금 근거")],
        )
        newer = _create_contract(
            session,
            plan_id=plan_id,
            member_id=member_id,
            company="B웨딩홀",
            confirmed_at=datetime(2026, 9, 1, tzinfo=UTC),
            payments=[
                ("계약금", 3_000_000, date(2099, 1, 1), PaymentStatus.PAID, "계약금 근거"),
                ("날짜 미정", 1_000_000, None, PaymentStatus.UNPAID, None),
                ("중도금", 5_000_000, date(2099, 2, 1), PaymentStatus.UNPAID, "중도금 근거"),
                ("잔금", 14_000_000, date(2099, 4, 30), PaymentStatus.UNPAID, "잔금 근거"),
            ],
        )
        _create_contract(
            session,
            plan_id=other_plan_id,
            member_id=other_member_id,
            company="다른 사용자 웨딩홀",
            confirmed_at=datetime(2026, 9, 2, tzinfo=UTC),
            payments=[("잔금", 10_000_000, date(2099, 1, 1), PaymentStatus.UNPAID, "비공개")],
        )
        older_id = older.id
        newer_id = newer.id
        session.commit()

    configuration = _configuration(str(database_engine.url), user_id)
    _override_dependencies(database_engine, configuration)
    try:
        response = TestClient(app).get("/api/contracts")

        assert response.status_code == 200
        payload = response.json()
        assert [item["id"] for item in payload["items"]] == [str(newer_id), str(older_id)]
        assert payload["items"][0]["nextPayment"] == {
            "contractId": str(newer_id),
            "company": "B웨딩홀",
            "name": "중도금",
            "amount": 5_000_000,
            "dueDate": "2099-02-01",
        }
        assert all(item["company"] != "다른 사용자 웨딩홀" for item in payload["items"])
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id, other_user_id])


def test_contract_detail_preserves_nullable_fields_and_hides_other_plan(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id, other_user_id])
    with Session(database_engine) as session:
        plan_id, member_id = _create_user_plan(session, user_id)
        other_plan_id, other_member_id = _create_user_plan(session, other_user_id)
        contract = _create_contract(
            session,
            plan_id=plan_id,
            member_id=member_id,
            company="A웨딩홀",
            confirmed_at=datetime(2026, 9, 1, tzinfo=UTC),
            payments=[("날짜 미정", 20_000_000, None, PaymentStatus.UNPAID, None)],
        )
        other_contract = _create_contract(
            session,
            plan_id=other_plan_id,
            member_id=other_member_id,
            company="다른 사용자 웨딩홀",
            confirmed_at=datetime(2026, 9, 1, tzinfo=UTC),
            payments=[("잔금", 20_000_000, date(2099, 4, 30), PaymentStatus.UNPAID, "비공개")],
        )
        contract_id = contract.id
        other_contract_id = other_contract.id
        session.commit()

    configuration = _configuration(str(database_engine.url), user_id)
    _override_dependencies(database_engine, configuration)
    try:
        client = TestClient(app)
        response = client.get(f"/api/contracts/{contract_id}")
        hidden = client.get(f"/api/contracts/{other_contract_id}")
        missing = client.get(f"/api/contracts/{uuid.uuid4()}")

        assert response.status_code == 200
        assert response.json()["payments"][0]["dueDate"] is None
        assert response.json()["payments"][0]["sourceText"] is None
        assert response.json()["cancellationTerms"][0]["sourceText"] is None
        assert hidden.status_code == 404
        assert missing.status_code == 404
        assert hidden.json() == missing.json()
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id, other_user_id])


def test_contract_list_without_current_plan_is_empty(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    configuration = _configuration(str(database_engine.url), user_id)
    _override_dependencies(database_engine, configuration)
    try:
        response = TestClient(app).get("/api/contracts")

        assert response.status_code == 200
        assert response.json() == {"items": []}
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_contract_responses_match_generated_and_committed_openapi(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    with Session(database_engine) as session:
        plan_id, member_id = _create_user_plan(session, user_id)
        contract = _create_contract(
            session,
            plan_id=plan_id,
            member_id=member_id,
            company="A웨딩홀",
            confirmed_at=datetime(2026, 9, 1, tzinfo=UTC),
            payments=[("잔금", 20_000_000, date(2099, 4, 30), PaymentStatus.UNPAID, "잔금 근거")],
        )
        contract_id = contract.id
        session.commit()

    configuration = _configuration(str(database_engine.url), user_id)
    _override_dependencies(database_engine, configuration)
    try:
        client = TestClient(app)
        list_response = client.get("/api/contracts")
        detail_response = client.get(f"/api/contracts/{contract_id}")
        generated_openapi = app.openapi()
        generated_schemas = generated_openapi["components"]["schemas"]
        Draft202012Validator(
            generated_openapi,
            format_checker=FormatChecker(),
        ).evolve(schema=generated_schemas["ContractListRead"]).validate(list_response.json())
        Draft202012Validator(
            generated_openapi,
            format_checker=FormatChecker(),
        ).evolve(schema=generated_schemas["ContractDetailRead"]).validate(detail_response.json())

        committed = yaml.safe_load(
            (PROJECT_ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
        )
        Draft202012Validator(
            committed,
            format_checker=FormatChecker(),
        ).evolve(schema=committed["components"]["schemas"]["ContractList"]).validate(
            list_response.json()
        )
        Draft202012Validator(
            committed,
            format_checker=FormatChecker(),
        ).evolve(schema=committed["components"]["schemas"]["ContractDetail"]).validate(
            detail_response.json()
        )
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])
