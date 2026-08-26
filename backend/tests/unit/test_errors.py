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
        raise RuntimeError("sensitive internal message")

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


def test_unexpected_error_does_not_expose_internal_message() -> None:
    client = TestClient(create_test_app(), raise_server_exceptions=False)

    response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "sensitive internal message" not in response.text
