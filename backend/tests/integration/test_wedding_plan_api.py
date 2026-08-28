import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.enums import AssetCategory, AssetOwnerType, WeddingPlanMemberRole
from app.domains.users.models import User
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember
from app.domains.wedding_plan.repository import WeddingPlanRepository
from app.domains.wedding_plan.schemas import MAX_BIGINT
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
        demo_user_login_id=f"plan-{user_id}",
        demo_user_display_name="Plan Demo",
        demo_user_email=None,
    )


def _override_dependencies(engine: Engine, configuration: Settings) -> None:
    def database_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database_session
    app.dependency_overrides[get_settings] = lambda: configuration


def _cleanup(engine: Engine, user_id: uuid.UUID) -> None:
    with Session(engine) as session:
        plan_ids = session.scalars(
            select(WeddingPlanMember.wedding_plan_id).where(WeddingPlanMember.user_id == user_id)
        ).all()
        if plan_ids:
            session.execute(Asset.__table__.delete().where(Asset.wedding_plan_id.in_(plan_ids)))
            session.execute(
                WeddingPlanMember.__table__.delete().where(
                    WeddingPlanMember.wedding_plan_id.in_(plan_ids)
                )
            )
            session.execute(WeddingPlan.__table__.delete().where(WeddingPlan.id.in_(plan_ids)))
        session.execute(User.__table__.delete().where(User.id == user_id))
        session.commit()


def test_plan_01_upsert_and_get_persist_member_and_asset(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _cleanup(database_engine, user_id)
    _override_dependencies(database_engine, configuration)

    try:
        client = TestClient(app)
        created = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": 30_000_000},
        )
        fetched = client.get("/api/wedding-plan")

        assert created.status_code == 200
        assert fetched.status_code == 200
        assert fetched.json() == created.json()
        assert set(created.json()) == {"id", "weddingDate", "availableAsset"}
        assert created.json()["weddingDate"] == "2027-05-15"
        assert created.json()["availableAsset"] == 30_000_000

        plan_id = uuid.UUID(created.json()["id"])
        with Session(database_engine) as session:
            member = session.scalar(
                select(WeddingPlanMember).where(
                    WeddingPlanMember.wedding_plan_id == plan_id,
                    WeddingPlanMember.user_id == user_id,
                )
            )
            asset = session.scalar(select(Asset).where(Asset.wedding_plan_id == plan_id))
            assert member is not None
            assert member.role == WeddingPlanMemberRole.OWNER
            assert asset is not None
            assert asset.owner_type == AssetOwnerType.JOINT
            assert asset.category == AssetCategory.CASH
            assert asset.amount == 30_000_000

        updated = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-06-01", "availableAsset": 35_000_000},
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "id": str(plan_id),
            "weddingDate": "2027-06-01",
            "availableAsset": 35_000_000,
        }
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)


def test_int64_max_asset_round_trips_without_precision_loss(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _cleanup(database_engine, user_id)
    _override_dependencies(database_engine, configuration)

    try:
        client = TestClient(app)
        created = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": MAX_BIGINT},
        )
        fetched = client.get("/api/wedding-plan")

        assert created.status_code == 200
        assert created.json()["availableAsset"] == MAX_BIGINT
        assert fetched.status_code == 200
        assert fetched.json()["availableAsset"] == MAX_BIGINT

        plan_id = uuid.UUID(created.json()["id"])
        with Session(database_engine) as session:
            stored_amount = session.scalar(
                select(Asset.amount).where(Asset.wedding_plan_id == plan_id)
            )
            assert stored_amount == MAX_BIGINT
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)


def test_upsert_available_asset_is_consistent_when_personal_asset_exists(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _cleanup(database_engine, user_id)
    _override_dependencies(database_engine, configuration)

    try:
        client = TestClient(app)
        created = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": 30_000_000},
        )
        assert created.status_code == 200
        plan_id = uuid.UUID(created.json()["id"])

        with Session(database_engine) as session:
            member = session.scalar(
                select(WeddingPlanMember).where(
                    WeddingPlanMember.wedding_plan_id == plan_id,
                    WeddingPlanMember.user_id == user_id,
                )
            )
            initial_asset = session.scalar(
                select(Asset).where(
                    Asset.wedding_plan_id == plan_id,
                    Asset.owner_type == AssetOwnerType.JOINT,
                    Asset.category == AssetCategory.CASH,
                    Asset.owner_member_id.is_(None),
                )
            )
            assert member is not None
            assert initial_asset is not None
            initial_asset_id = initial_asset.id
            personal_asset_id = uuid.uuid4()
            additional_joint_asset_id = uuid.uuid4()
            session.add_all(
                [
                    Asset(
                        id=personal_asset_id,
                        wedding_plan_id=plan_id,
                        owner_member_id=member.id,
                        owner_type=AssetOwnerType.PERSONAL,
                        category=AssetCategory.CASH,
                        amount=10_000_000,
                    ),
                    Asset(
                        id=additional_joint_asset_id,
                        wedding_plan_id=plan_id,
                        owner_member_id=None,
                        owner_type=AssetOwnerType.JOINT,
                        category=AssetCategory.CASH,
                        amount=5_000_000,
                    ),
                ]
            )
            session.commit()

        updated = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": 40_000_000},
        )
        fetched = client.get("/api/wedding-plan")
        repeated = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": 40_000_000},
        )

        assert updated.status_code == 200
        assert updated.json()["availableAsset"] == 40_000_000
        assert fetched.status_code == 200
        assert fetched.json()["availableAsset"] == 40_000_000
        assert repeated.status_code == 200
        assert repeated.json()["availableAsset"] == 40_000_000

        with Session(database_engine) as session:
            initial_asset = session.get(Asset, initial_asset_id)
            personal_asset = session.get(Asset, personal_asset_id)
            additional_joint_asset = session.get(Asset, additional_joint_asset_id)
            assert initial_asset is not None
            assert initial_asset.amount == 40_000_000
            assert personal_asset is not None
            assert personal_asset.amount == 10_000_000
            assert additional_joint_asset is not None
            assert additional_joint_asset.amount == 5_000_000
            assert WeddingPlanRepository(session).available_asset(plan_id) == 55_000_000
            asset_count = session.scalar(
                select(func.count()).select_from(Asset).where(Asset.wedding_plan_id == plan_id)
            )
            assert asset_count == 3
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)


def test_plan_02_and_caller_selected_user_are_rejected(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _override_dependencies(database_engine, configuration)
    try:
        client = TestClient(app)
        negative = client.put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": -1},
        )
        selected_user = client.put(
            "/api/wedding-plan",
            json={
                "weddingDate": "2027-05-15",
                "availableAsset": 30_000_000,
                "userId": str(uuid.uuid4()),
            },
        )

        assert negative.status_code == 400
        assert negative.json()["error"]["code"] == "VALIDATION_ERROR"
        assert selected_user.status_code == 400
        assert selected_user.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)


def test_missing_plan_returns_contract_404(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _cleanup(database_engine, user_id)
    _override_dependencies(database_engine, configuration)
    try:
        response = TestClient(app).get("/api/wedding-plan")

        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "현재 WeddingPlan이 없습니다.",
                "details": {},
            }
        }
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)


def test_current_plan_does_not_leak_another_users_plan(database_engine: Engine) -> None:
    demo_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), demo_user_id)
    _cleanup(database_engine, demo_user_id)
    _cleanup(database_engine, other_user_id)
    with Session(database_engine) as session:
        other_plan = WeddingPlan(id=uuid.uuid4(), wedding_date=date(2027, 5, 15))
        session.add(
            User(
                id=other_user_id,
                login_id=f"other-{other_user_id}",
                password_hash="$2b$12$not-a-login-credential",
                display_name="Other User",
            )
        )
        session.add(other_plan)
        session.add(
            WeddingPlanMember(
                id=uuid.uuid4(),
                wedding_plan_id=other_plan.id,
                user_id=other_user_id,
                role=WeddingPlanMemberRole.OWNER,
            )
        )
        session.add(
            Asset(
                id=uuid.uuid4(),
                wedding_plan_id=other_plan.id,
                owner_member_id=None,
                owner_type=AssetOwnerType.JOINT,
                category=AssetCategory.CASH,
                amount=30_000_000,
            )
        )
        session.commit()

    _override_dependencies(database_engine, configuration)
    try:
        response = TestClient(app).get("/api/wedding-plan")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, demo_user_id)
        _cleanup(database_engine, other_user_id)


def test_concurrent_upserts_create_only_one_current_plan(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _cleanup(database_engine, user_id)
    _override_dependencies(database_engine, configuration)

    def upsert() -> tuple[int, str]:
        response = TestClient(app).put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": 30_000_000},
        )
        return response.status_code, response.json().get("id", "")

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _index: upsert(), range(4)))

        assert {status_code for status_code, _plan_id in results} == {200}
        assert len({plan_id for _status_code, plan_id in results}) == 1
        with Session(database_engine) as session:
            membership_count = session.scalar(
                select(func.count())
                .select_from(WeddingPlanMember)
                .where(WeddingPlanMember.user_id == user_id)
            )
            assert membership_count == 1
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)


def test_wedding_plan_response_matches_generated_openapi(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    configuration = _configuration(str(database_engine.url), user_id)
    _cleanup(database_engine, user_id)
    _override_dependencies(database_engine, configuration)
    try:
        response = TestClient(app).put(
            "/api/wedding-plan",
            json={"weddingDate": "2027-05-15", "availableAsset": 30_000_000},
        )
        generated_openapi = app.openapi()
        validator = Draft202012Validator(
            generated_openapi,
            format_checker=FormatChecker(),
        ).evolve(schema=generated_openapi["components"]["schemas"]["WeddingPlanRead"])

        validator.validate(response.json())
        request_schema = generated_openapi["components"]["schemas"]["WeddingPlanUpsert"]
        assert set(request_schema["properties"]) == {"weddingDate", "availableAsset"}
        assert request_schema["properties"]["availableAsset"]["maximum"] == (
            9_223_372_036_854_775_807
        )
        assert request_schema["properties"]["availableAsset"]["description"] == (
            "Representative joint cash asset entered during WeddingPlan setup."
        )

        contract = yaml.safe_load(
            (PROJECT_ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
        )
        contract_validator = Draft202012Validator(
            contract,
            format_checker=FormatChecker(),
        ).evolve(schema=contract["components"]["schemas"]["WeddingPlan"])
        contract_validator.validate(response.json())
        assert (
            contract["components"]["schemas"]["WeddingPlan"]["properties"]["availableAsset"][
                "description"
            ]
            == "Representative joint cash asset entered during WeddingPlan setup."
        )
        assert set(contract["paths"]["/wedding-plan"]["get"]["responses"]) == {"200", "404"}
        assert set(contract["paths"]["/wedding-plan"]["put"]["responses"]) == {"200", "400"}
    finally:
        app.dependency_overrides.clear()
        _cleanup(database_engine, user_id)
