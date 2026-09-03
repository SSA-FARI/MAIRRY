import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from app.domains.contracts.models import CancellationTerm, Contract, Payment
from app.domains.documents.models import Document
from app.domains.users.models import User
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember
from app.main import app

pytestmark = pytest.mark.integration
BACKEND_ROOT = Path(__file__).resolve().parents[2]


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
        demo_user_login_id=f"chat-{user_id}",
        demo_user_display_name="Chat Demo",
        demo_user_email=None,
    )


def _override_dependencies(engine: Engine, configuration: Settings) -> None:
    def database_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database_session
    app.dependency_overrides[get_settings] = lambda: configuration


def _create_plan_with_contract(
    session: Session,
    user_id: uuid.UUID,
    *,
    company: str,
    amount: int,
    source_text: str,
) -> uuid.UUID:
    plan_id = uuid.uuid4()
    member_id = uuid.uuid4()
    document_id = uuid.uuid4()
    session.add(
        User(
            id=user_id,
            login_id=f"chat-{user_id}",
            password_hash="$2b$12$not-a-login-credential",
            display_name="Chat Demo",
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
    session.add(
        Asset(
            wedding_plan_id=plan_id,
            owner_member_id=None,
            owner_type=AssetOwnerType.JOINT,
            category=AssetCategory.CASH,
            amount=30_000_000,
            label="현재 가용자금",
        )
    )
    document = Document(
        id=document_id,
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
        document_id=document_id,
        document_type=DocumentType.WEDDING_HALL,
        company=company,
        total_price=23_000_000,
        status=ContractStatus.CONFIRMED,
        confirmed_by_member_id=member_id,
        confirmed_at=datetime(2026, 9, 3, tzinfo=UTC),
    )
    contract.payments = [
        Payment(
            name="계약금",
            amount=3_000_000,
            due_date=date(2026, 9, 1),
            status=PaymentStatus.PAID,
            source_text="계약금 3,000,000원 지급 완료",
        ),
        Payment(
            name="잔금",
            amount=amount,
            due_date=date(2099, 4, 30),
            status=PaymentStatus.UNPAID,
            source_text=source_text,
        ),
    ]
    contract.cancellation_terms = [
        CancellationTerm(
            summary="예식 90일 전까지 계약금 환급",
            source_text="예식 90일 전까지 계약금을 환급합니다.",
        )
    ]
    session.add(contract)
    return contract.id


def _cleanup(engine: Engine, user_ids: list[uuid.UUID]) -> None:
    with Session(engine) as session:
        plan_ids = list(
            session.scalars(
                select(WeddingPlanMember.wedding_plan_id).where(
                    WeddingPlanMember.user_id.in_(user_ids)
                )
            )
        )
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
            session.query(Asset).filter(Asset.wedding_plan_id.in_(plan_ids)).delete(
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


def test_chat_golden_path_uses_owned_contract_and_finance_data(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id, other_user_id])
    with Session(database_engine) as session:
        contract_id = _create_plan_with_contract(
            session,
            user_id,
            company="A웨딩홀",
            amount=20_000_000,
            source_text="잔금 20,000,000원은 2099년 4월 30일까지",
        )
        _create_plan_with_contract(
            session,
            other_user_id,
            company="비공개 웨딩홀",
            amount=99_000_000,
            source_text="다른 사용자의 비공개 근거",
        )
        session.commit()

    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    client = TestClient(app)
    try:
        schedule = client.post("/api/chat", json={"message": "가장 가까운 잔금일은 언제야?"})
        finance = client.post("/api/chat", json={"message": "남은 금액과 예상 잔액 알려줘"})
        simulation = client.post(
            "/api/chat",
            json={"message": "가전 비용 300만 원을 추가하면 괜찮아?"},
        )
        cancellation = client.post("/api/chat", json={"message": "웨딩홀 취소 조건 알려줘"})

        assert schedule.status_code == finance.status_code == simulation.status_code == 200
        assert "2099-04-30" in schedule.json()["answer"]
        assert schedule.json()["citations"][0]["contractId"] == str(contract_id)
        assert "비공개" not in str(schedule.json())
        assert finance.json()["calculation"]["expectedBalance"] == 10_000_000
        assert simulation.json()["calculation"]["simulatedExpectedBalance"] == 7_000_000
        assert cancellation.json()["citations"][0]["sourceText"].startswith("예식 90일 전")
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id, other_user_id])


def test_chat_without_plan_returns_insufficient_data_without_numbers(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        response = TestClient(app).post("/api/chat", json={"message": "남은 금액 알려줘"})

        assert response.status_code == 200
        assert response.json()["answerType"] == "NOT_FOUND"
        assert response.json()["calculation"] is None
        assert not any(character.isdigit() for character in response.json()["answer"])
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])
