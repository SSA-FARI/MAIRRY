import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.users.models import User

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for database integration tests")
    return database_url


def test_duplicate_login_id_is_rejected() -> None:
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
    login_id = f"duplicate-{uuid.uuid4()}"

    with Session(engine) as session:
        first_user = User(
            login_id=login_id,
            password_hash="$2b$12$.....................................................",
            display_name="First User",
        )
        second_user = User(
            login_id=login_id,
            password_hash="$2b$12$.....................................................",
            display_name="Second User",
        )
        session.add(first_user)
        session.commit()

        try:
            session.add(second_user)
            with pytest.raises(IntegrityError):
                session.commit()
        finally:
            session.rollback()
            session.delete(first_user)
            session.commit()

    engine.dispose()
