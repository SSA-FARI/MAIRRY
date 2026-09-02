import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from datetime import date

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
        demo_user_login_id=f"mut-{user_id}",
        demo_user_display_name="Contract Mutation Demo",
        demo_user_email=None,
    )


def _override_dependencies(engine: Engine, configuration: Settings) -> None:
    def database_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database_session
    app.dependency_overrides[get_settings] = lambda: configuration


def _create_context(
    engine: Engine,
    user_id: uuid.UUID,
    *,
    extraction_raw: dict[str, object] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    plan_id = uuid.uuid4()
    member_id = uuid.uuid4()
    document_id = uuid.uuid4()
    contract_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            User(
                id=user_id,
                login_id=f"mut-{user_id}",
                password_hash="$2b$12$not-a-login-credential",
                display_name="Contract Mutation Demo",
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
                id=uuid.uuid4(),
                wedding_plan_id=plan_id,
                owner_member_id=None,
                owner_type=AssetOwnerType.JOINT,
                category=AssetCategory.CASH,
                amount=30_000_000,
            )
        )
        document = Document(
            id=document_id,
            wedding_plan_id=plan_id,
            uploaded_by_member_id=member_id,
            original_filename="contract.pdf",
            file_url=f"documents/{document_id}.pdf",
            content_type="application/pdf",
            analysis_status=DocumentStatus.CONFIRMED,
            extraction_raw=extraction_raw,
        )
        session.add(document)
        session.flush()
        contract = Contract(
            id=contract_id,
            wedding_plan_id=plan_id,
            document_id=document_id,
            document_type=DocumentType.WEDDING_HALL,
            company="기존 웨딩홀",
            total_price=20_000_000,
            status=ContractStatus.CONFIRMED,
            confirmed_by_member_id=member_id,
        )
        contract.payments = [
            Payment(
                name="기존 잔금",
                amount=20_000_000,
                due_date=date(2099, 4, 30),
                status=PaymentStatus.UNPAID,
                source_text="기존 근거",
            )
        ]
        contract.cancellation_terms = [
            CancellationTerm(summary="기존 취소조건", source_text="기존 취소 근거")
        ]
        session.add(contract)
        session.commit()
    return contract_id, document_id


def _cleanup(engine: Engine, user_ids: list[uuid.UUID]) -> None:
    with Session(engine) as session:
        plan_ids = session.scalars(
            select(WeddingPlanMember.wedding_plan_id).where(WeddingPlanMember.user_id.in_(user_ids))
        ).all()
        if plan_ids:
            contract_ids = session.scalars(
                select(Contract.id).where(Contract.wedding_plan_id.in_(plan_ids))
            ).all()
            if contract_ids:
                session.query(CancellationTerm).filter(
                    CancellationTerm.contract_id.in_(contract_ids)
                ).delete(synchronize_session=False)
                session.query(Payment).filter(Payment.contract_id.in_(contract_ids)).delete(
                    synchronize_session=False
                )
                session.query(Contract).filter(Contract.id.in_(contract_ids)).delete(
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


def _updated_payload() -> dict[str, object]:
    return {
        "documentType": "WEDDING_HALL",
        "company": "수정 웨딩홀",
        "totalPrice": 23_000_000,
        "payments": [
            {
                "name": "수정 잔금",
                "amount": 15_000_000,
                "dueDate": "2099-05-01",
                "status": "UNPAID",
                "sourceText": "수정 근거",
            }
        ],
        "cancellationTerms": [{"summary": "수정 취소조건", "sourceText": "수정 취소 근거"}],
    }


def test_contract_01_update_replaces_children_and_finance_values(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    contract_id, _document_id = _create_context(database_engine, user_id)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(f"/api/contracts/{contract_id}", json=_updated_payload())
        finance = client.get("/api/finance/summary")

        assert response.status_code == 200
        assert response.json()["company"] == "수정 웨딩홀"
        assert response.json()["payments"] == [
            {
                "name": "수정 잔금",
                "amount": 15_000_000,
                "dueDate": "2099-05-01",
                "status": "UNPAID",
                "sourceText": "수정 근거",
            }
        ]
        assert response.json()["cancellationTerms"] == [
            {"summary": "수정 취소조건", "sourceText": "수정 취소 근거"}
        ]
        assert finance.status_code == 200
        assert finance.json()["remainingExpense"] == 15_000_000
        with Session(database_engine) as session:
            document = session.get(Document, response.json()["documentId"])
            assert document is not None
            assert document.document_type == DocumentType.WEDDING_HALL.value
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_contract_02_invalid_update_keeps_existing_values(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    contract_id, _document_id = _create_context(database_engine, user_id)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        payload = _updated_payload()
        payload["payments"] = []
        client = TestClient(app)
        response = client.put(f"/api/contracts/{contract_id}", json=payload)
        unchanged = client.get(f"/api/contracts/{contract_id}")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "EXTRACTION_VALIDATION_ERROR"
        assert unchanged.json()["company"] == "기존 웨딩홀"
        assert unchanged.json()["payments"][0]["amount"] == 20_000_000
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


@pytest.mark.parametrize(
    ("extraction_raw", "expected_status"),
    [({"preserved": True}, DocumentStatus.REVIEW_REQUIRED), (None, DocumentStatus.FAILED)],
)
def test_contract_03_04_05_delete_preserves_and_reopens_document(
    database_engine: Engine,
    extraction_raw: dict[str, object] | None,
    expected_status: DocumentStatus,
) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    contract_id, document_id = _create_context(
        database_engine,
        user_id,
        extraction_raw=extraction_raw,
    )
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.delete(f"/api/contracts/{contract_id}")

        assert response.status_code == 204
        assert response.content == b""
        assert client.get(f"/api/contracts/{contract_id}").status_code == 404
        assert client.get("/api/contracts").json() == {"items": []}
        assert client.get("/api/finance/summary").json()["remainingExpense"] == 0
        with Session(database_engine) as session:
            assert session.get(Contract, contract_id) is None
            document = session.get(Document, document_id)
            assert document is not None
            assert document.analysis_status == expected_status
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_contract_06_other_plan_cannot_update_or_delete(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id, other_user_id])
    _create_context(database_engine, user_id)
    other_contract_id, _document_id = _create_context(database_engine, other_user_id)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        update = client.put(f"/api/contracts/{other_contract_id}", json=_updated_payload())
        delete = client.delete(f"/api/contracts/{other_contract_id}")

        assert update.status_code == 404
        assert delete.status_code == 404
        with Session(database_engine) as session:
            other_contract = session.get(Contract, other_contract_id)
            assert other_contract is not None
            assert other_contract.company == "기존 웨딩홀"
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id, other_user_id])
