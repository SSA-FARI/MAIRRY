import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, register_exception_handlers


def create_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    def raise_app_error() -> None:
        raise AppError(
            code=ErrorCode.INVALID_STATE,
            message="현재 상태에서는 처리할 수 없습니다.",
            status_code=409,
        )

    @app.get("/unexpected-error")
    def raise_unexpected_error() -> None:
        sensitive_message = "sensitive internal message"
        raise RuntimeError(sensitive_message)

    return app


def test_app_error_is_serialized_with_common_shape() -> None:
    client = TestClient(create_test_app())

    response = client.get("/app-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "INVALID_STATE",
            "message": "현재 상태에서는 처리할 수 없습니다.",
            "details": {},
        }
    }


def test_unexpected_error_keeps_sanitized_traceback_without_internal_message(caplog) -> None:
    client = TestClient(create_test_app(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    trace_id = response.json()["error"]["details"]["traceId"]
    assert "sensitive internal message" not in response.text
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.exc_info is not None
    assert record.exc_info[2] is not None
    assert "raise_unexpected_error" in caplog.text
    assert "sensitive internal message" not in caplog.text
    assert "unexpected error details redacted" in caplog.text
    assert f"traceId={trace_id}" in caplog.text
