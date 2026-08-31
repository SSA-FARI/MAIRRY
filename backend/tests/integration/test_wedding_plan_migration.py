import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "20260827_0002"


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


def test_wedding_plan_migration_upgrades_and_downgrades() -> None:
    environment, database_url = _migration_environment()
    engine = create_engine(database_url)

    _run_alembic(environment, "upgrade", "head")
    inspector = inspect(engine)
    assert inspector.has_table("wedding_plans")
    assert inspector.has_table("wedding_plan_members")
    assert inspector.has_table("assets")
    assert {column["name"] for column in inspector.get_columns("wedding_plans")} == {
        "id",
        "wedding_date",
        "status",
        "created_at",
        "updated_at",
    }
    assert {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("wedding_plan_members")
    } == {("wedding_plan_id", "user_id")}
    assert {index["name"] for index in inspector.get_indexes("assets")} == {
        "ix_assets_wedding_plan_id"
    }

    _run_alembic(environment, "downgrade", PREVIOUS_REVISION)
    downgraded = inspect(engine)
    assert not downgraded.has_table("assets")
    assert not downgraded.has_table("wedding_plan_members")
    assert not downgraded.has_table("wedding_plans")

    _run_alembic(environment, "upgrade", "head")
    assert inspect(engine).has_table("wedding_plans")
    engine.dispose()
