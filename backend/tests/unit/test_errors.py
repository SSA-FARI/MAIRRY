import logging
from io import StringIO

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


def test_unexpected_error_formats_sanitized_traceback_with_stream_handler() -> None:
    client = TestClient(create_test_app(), raise_server_exceptions=False)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    error_logger = logging.getLogger("app.core.errors")
    error_logger.addHandler(handler)

    try:
        response = client.get("/unexpected-error")
    finally:
        error_logger.removeHandler(handler)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    trace_id = response.json()["error"]["details"]["traceId"]
    assert "sensitive internal message" not in response.text
    log_output = stream.getvalue()
    assert "raise_unexpected_error" in log_output
    assert "test_errors.py" in log_output
    assert "sensitive internal message" not in log_output
    assert f"traceId={trace_id}" in log_output
