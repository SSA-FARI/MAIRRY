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
    DocumentStatus,
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
        demo_user_login_id=f"confirm-{user_id}",
        demo_user_display_name="Document Confirm Demo",
        demo_user_email=None,
    )


def _override_dependencies(engine: Engine, configuration: Settings) -> None:
    def database_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database_session
    app.dependency_overrides[get_settings] = lambda: configuration


def _create_document(
    engine: Engine,
    user_id: uuid.UUID,
    *,
    status: DocumentStatus,
    extraction_raw: dict[str, object] | None = None,
    available_asset: int = 30_000_000,
) -> uuid.UUID:
    plan_id = uuid.uuid4()
    member_id = uuid.uuid4()
    document_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            User(
                id=user_id,
                login_id=f"confirm-{user_id}",
                password_hash="$2b$12$not-a-login-credential",
                display_name="Document Confirm Demo",
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
                amount=available_asset,
            )
        )
        session.add(
            Document(
                id=document_id,
                wedding_plan_id=plan_id,
                uploaded_by_member_id=member_id,
                original_filename="contract.pdf",
                file_url=f"documents/{document_id}.pdf",
                content_type="application/pdf",
                analysis_status=status,
                extraction_raw=extraction_raw,
            )
        )
        session.commit()
    return document_id


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


def _confirm_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "documentType": "WEDDING_HALL",
        "company": "수정 웨딩홀",
        "totalPrice": 23_000_000,
        "payments": [
            {
                "name": "잔금",
                "amount": 20_000_000,
                "dueDate": "2099-04-30",
                "status": "UNPAID",
                "sourceText": "잔금 20,000,000원은 2099년 4월 30일까지",
            }
        ],
        "cancellationTerms": [{"summary": "취소조건", "sourceText": "취소 근거"}],
    }
    payload.update(overrides)
    return payload


def test_review_01_confirm_saves_edited_values(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=DocumentStatus.REVIEW_REQUIRED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(
            f"/api/documents/{document_id}/confirm",
            json=_confirm_payload(company="검수 후 수정한 웨딩홀"),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["company"] == "검수 후 수정한 웨딩홀"
        assert body["status"] == "CONFIRMED"
        assert body["payments"][0]["amount"] == 20_000_000
        assert body["payments"][0]["sourceText"] == "잔금 20,000,000원은 2099년 4월 30일까지"
        with Session(database_engine) as session:
            document = session.get(Document, document_id)
            assert document is not None
            assert document.analysis_status == DocumentStatus.CONFIRMED
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_review_02_missing_company_blocks_confirmation(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=DocumentStatus.REVIEW_REQUIRED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(
            f"/api/documents/{document_id}/confirm",
            json=_confirm_payload(company=""),
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "EXTRACTION_VALIDATION_ERROR"
        with Session(database_engine) as session:
            document = session.get(Document, document_id)
            assert document is not None
            assert document.analysis_status == DocumentStatus.REVIEW_REQUIRED
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_review_03_unconfirmed_document_excluded_from_finance(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=DocumentStatus.REVIEW_REQUIRED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        before = client.get("/api/finance/summary")
        assert before.status_code == 200
        assert before.json()["remainingExpense"] == 0
        assert before.json()["expectedBalance"] == 30_000_000

        confirm = client.put(f"/api/documents/{document_id}/confirm", json=_confirm_payload())
        assert confirm.status_code == 200

        after = client.get("/api/finance/summary")
        assert after.json()["remainingExpense"] == 20_000_000
        assert after.json()["expectedBalance"] == 10_000_000
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_review_04_null_payment_amount_blocks_confirmation(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=DocumentStatus.REVIEW_REQUIRED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        payload = _confirm_payload()
        payload["payments"][0]["amount"] = None  # type: ignore[index]
        response = client.put(f"/api/documents/{document_id}/confirm", json=payload)

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "EXTRACTION_VALIDATION_ERROR"
        with Session(database_engine) as session:
            document = session.get(Document, document_id)
            assert document is not None
            assert document.analysis_status == DocumentStatus.REVIEW_REQUIRED
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_review_05_empty_payments_blocks_confirmation(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=DocumentStatus.REVIEW_REQUIRED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(
            f"/api/documents/{document_id}/confirm",
            json=_confirm_payload(payments=[]),
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "EXTRACTION_VALIDATION_ERROR"
        with Session(database_engine) as session:
            document = session.get(Document, document_id)
            assert document is not None
            assert document.analysis_status == DocumentStatus.REVIEW_REQUIRED
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_review_06_manual_entry_from_failed_document_drops_source_text(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=DocumentStatus.FAILED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(
            f"/api/documents/{document_id}/confirm",
            json=_confirm_payload(),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CONFIRMED"
        assert body["payments"][0]["sourceText"] is None
        assert body["cancellationTerms"][0]["sourceText"] is None
        with Session(database_engine) as session:
            document = session.get(Document, document_id)
            assert document is not None
            assert document.analysis_status == DocumentStatus.CONFIRMED
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


@pytest.mark.parametrize(
    "status_value",
    [DocumentStatus.UPLOADED, DocumentStatus.PROCESSING, DocumentStatus.CONFIRMED],
)
def test_confirm_rejects_invalid_document_state(
    database_engine: Engine,
    status_value: DocumentStatus,
) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    document_id = _create_document(database_engine, user_id, status=status_value)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(f"/api/documents/{document_id}/confirm", json=_confirm_payload())

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_STATE"
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])


def test_confirm_returns_404_when_document_missing(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    _cleanup(database_engine, [user_id])
    _create_document(database_engine, user_id, status=DocumentStatus.REVIEW_REQUIRED)
    _override_dependencies(database_engine, _configuration(str(database_engine.url), user_id))
    try:
        client = TestClient(app)
        response = client.put(f"/api/documents/{uuid.uuid4()}/confirm", json=_confirm_payload())

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, [user_id])
