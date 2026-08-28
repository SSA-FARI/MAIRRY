import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "20260827_0001"


def _migration_environment() -> tuple[dict[str, str], str]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for migration integration tests")

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return environment, database_url


def _run_alembic(environment: dict[str, str], *arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_users_migration_upgrades_and_downgrades() -> None:
    environment, database_url = _migration_environment()
    engine = create_engine(database_url)

    _run_alembic(environment, "upgrade", "head")
    inspector = inspect(engine)
    assert inspector.has_table("users")
    columns = {column["name"]: column for column in inspector.get_columns("users")}
    assert list(columns) == [
        "id",
        "login_id",
        "password_hash",
        "display_name",
        "email",
        "created_at",
        "updated_at",
    ]
    assert columns["email"]["nullable"] is True
    assert all(columns[name]["nullable"] is False for name in columns if name != "email")
    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("users")
    }
    assert unique_columns == {("email",), ("login_id",)}
    non_constraint_indexes = [
        index for index in inspector.get_indexes("users") if not index.get("duplicates_constraint")
    ]
    assert non_constraint_indexes == []

    _run_alembic(environment, "downgrade", PREVIOUS_REVISION)
    assert not inspect(engine).has_table("users")

    _run_alembic(environment, "upgrade", "head")
    assert inspect(engine).has_table("users")

    engine.dispose()
