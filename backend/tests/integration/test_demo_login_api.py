import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.domains.auth.passwords import create_unusable_demo_password_hash
from app.domains.users.models import User
from app.main import app

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url is None or not (make_url(database_url).database or "").endswith("_test"):
        pytest.skip("an isolated *_test PostgreSQL database is required")
    return database_url


@pytest.fixture(scope="module")
def database_engine() -> Engine:
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


def _configuration(database_url: str, *, user_id: uuid.UUID, login_id: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        demo_user_id=user_id,
        demo_user_login_id=login_id,
        demo_user_display_name="Configured Demo",
        demo_user_email=None,
    )


def _delete_test_users(engine: Engine, *, user_id: uuid.UUID, login_id: str) -> None:
    with Session(engine) as session:
        session.execute(
            User.__table__.delete().where(or_(User.id == user_id, User.login_id == login_id))
        )
        session.commit()


def _use_configuration(configuration: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: configuration


def test_demo_login_without_body_creates_user_once_and_returns_public_profile(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    login_id = f"demo-{uuid.uuid4()}"
    configuration = _configuration(str(database_engine.url), user_id=user_id, login_id=login_id)
    _delete_test_users(database_engine, user_id=user_id, login_id=login_id)
    _use_configuration(configuration)

    try:
        with TestClient(app) as client:
            first_response = client.post("/api/v1/auth/demo-login")
            second_response = client.post("/api/v1/auth/demo-login")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        expected_payload = {
            "user": {
                "id": str(user_id),
                "loginId": login_id,
                "displayName": "Configured Demo",
                "email": None,
            },
            "mode": "DEMO",
        }
        assert first_response.json() == expected_payload
        assert second_response.json() == expected_payload
        assert "password" not in first_response.text.lower()
        assert "token" not in first_response.text.lower()

        with Session(database_engine) as session:
            users = list(session.scalars(select(User).where(User.id == user_id)))
            assert len(users) == 1
            assert users[0].password_hash.startswith(("$2a$", "$2b$", "$2y$"))
            original_hash = users[0].password_hash

        with TestClient(app) as client:
            client.post("/api/v1/auth/demo-login")
        with Session(database_engine) as session:
            assert session.get(User, user_id).password_hash == original_hash
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _delete_test_users(database_engine, user_id=user_id, login_id=login_id)


def test_existing_demo_user_uses_database_profile_without_changing_hash(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    login_id = f"existing-{uuid.uuid4()}"
    password_hash = create_unusable_demo_password_hash()
    with Session(database_engine) as session:
        session.add(
            User(
                id=user_id,
                login_id=login_id,
                password_hash=password_hash,
                display_name="Persisted Demo",
                email="persisted@example.test",
            )
        )
        session.commit()

    configuration = _configuration(
        str(database_engine.url), user_id=user_id, login_id="configured-different-login"
    )
    _use_configuration(configuration)
    try:
        response = TestClient(app).post("/api/v1/auth/demo-login")

        assert response.status_code == 200
        assert response.json()["user"] == {
            "id": str(user_id),
            "loginId": login_id,
            "displayName": "Persisted Demo",
            "email": "persisted@example.test",
        }
        with Session(database_engine) as session:
            assert session.get(User, user_id).password_hash == password_hash
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _delete_test_users(database_engine, user_id=user_id, login_id=login_id)


def test_demo_login_ignores_caller_selected_user_and_requires_no_jwt(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    login_id = f"selected-{uuid.uuid4()}"
    configuration = _configuration(str(database_engine.url), user_id=user_id, login_id=login_id)
    _delete_test_users(database_engine, user_id=user_id, login_id=login_id)
    _use_configuration(configuration)
    try:
        response = TestClient(app).post(
            "/api/v1/auth/demo-login",
            json={"userId": str(uuid.uuid4())},
        )

        assert response.status_code == 200
        assert response.json()["user"]["id"] == str(user_id)
        assert set(response.json()) == {"user", "mode"}
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _delete_test_users(database_engine, user_id=user_id, login_id=login_id)


def test_concurrent_demo_logins_create_one_user(database_engine: Engine) -> None:
    user_id = uuid.uuid4()
    login_id = f"concurrent-{uuid.uuid4()}"
    configuration = _configuration(str(database_engine.url), user_id=user_id, login_id=login_id)
    _delete_test_users(database_engine, user_id=user_id, login_id=login_id)
    _use_configuration(configuration)

    def login() -> tuple[int, dict[str, Any]]:
        response = TestClient(app).post("/api/v1/auth/demo-login")
        return response.status_code, response.json()

    try:
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _index: login(), range(6)))

        assert all(status_code == 200 for status_code, _payload in results)
        assert {payload["user"]["id"] for _status, payload in results} == {str(user_id)}
        with Session(database_engine) as session:
            count = session.scalar(select(func.count()).select_from(User).where(User.id == user_id))
            assert count == 1
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _delete_test_users(database_engine, user_id=user_id, login_id=login_id)


def test_unique_profile_conflict_returns_sanitized_configuration_error(
    database_engine: Engine,
) -> None:
    existing_user_id = uuid.uuid4()
    configured_user_id = uuid.uuid4()
    login_id = f"conflict-{uuid.uuid4()}"
    with Session(database_engine) as session:
        session.add(
            User(
                id=existing_user_id,
                login_id=login_id,
                password_hash=create_unusable_demo_password_hash(),
                display_name="Existing User",
            )
        )
        session.commit()

    configuration = _configuration(
        str(database_engine.url), user_id=configured_user_id, login_id=login_id
    )
    _use_configuration(configuration)
    try:
        response = TestClient(app).post("/api/v1/auth/demo-login")

        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "CONFIGURATION_ERROR",
                "message": "Demo User 설정을 확인해 주세요.",
                "details": {},
            }
        }
        assert str(configured_user_id) not in response.text
        with Session(database_engine) as session:
            assert session.get(User, configured_user_id) is None
            assert session.get(User, existing_user_id) is not None
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _delete_test_users(
            database_engine,
            user_id=existing_user_id,
            login_id=login_id,
        )


def test_demo_login_response_matches_generated_openapi(
    database_engine: Engine,
) -> None:
    user_id = uuid.uuid4()
    login_id = f"contract-{uuid.uuid4()}"
    configuration = _configuration(str(database_engine.url), user_id=user_id, login_id=login_id)
    _delete_test_users(database_engine, user_id=user_id, login_id=login_id)
    _use_configuration(configuration)
    try:
        response = TestClient(app).post("/api/v1/auth/demo-login")
        generated_openapi = app.openapi()
        validator = Draft202012Validator(
            generated_openapi,
            format_checker=FormatChecker(),
        ).evolve(schema=generated_openapi["components"]["schemas"]["DemoLoginResponse"])

        assert response.status_code == 200
        validator.validate(response.json())
        generated_operation = generated_openapi["paths"]["/api/v1/auth/demo-login"]["post"]
        assert "requestBody" not in generated_operation
        assert generated_operation["security"] == []
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _delete_test_users(database_engine, user_id=user_id, login_id=login_id)
