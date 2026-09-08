import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_head_returns_ok_without_body() -> None:
    response = TestClient(app).head("/api/health")

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_health_rejects_unsupported_methods(method: str) -> None:
    response = TestClient(app).request(method, "/api/health")

    assert response.status_code == 405
