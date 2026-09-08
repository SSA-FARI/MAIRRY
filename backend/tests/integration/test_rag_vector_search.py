import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

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


def test_pgvector_orders_and_limits_ten_thousand_vectors_in_database(
    database_engine: Engine,
) -> None:
    query_vector = "[1," + "0," * 1534 + "0]"
    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TEMP TABLE rag_vector_benchmark (
                    id integer PRIMARY KEY,
                    embedding vector(1536) NOT NULL
                ) ON COMMIT DROP
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO rag_vector_benchmark (id, embedding)
                SELECT value,
                       ('[1,' || (10000 - value)::text || ',' ||
                        repeat('0,', 1533) || '0]')::vector(1536)
                FROM generate_series(1, 10000) AS value
                """
            )
        )
        rows = (
            connection.execute(
                text(
                    """
                SELECT id
                FROM rag_vector_benchmark
                ORDER BY embedding <=> CAST(:query_vector AS vector)
                LIMIT 5
                """
                ),
                {"query_vector": query_vector},
            )
            .scalars()
            .all()
        )
        plan = "\n".join(
            row[0]
            for row in connection.execute(
                text(
                    """
                    EXPLAIN (COSTS OFF)
                    SELECT id
                    FROM rag_vector_benchmark
                    ORDER BY embedding <=> CAST(:query_vector AS vector)
                    LIMIT 5
                    """
                ),
                {"query_vector": query_vector},
            )
        )

    assert rows == [10000, 9999, 9998, 9997, 9996]
    assert "Limit" in plan
