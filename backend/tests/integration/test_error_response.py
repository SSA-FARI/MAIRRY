from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_request_validation_uses_common_error_shape() -> None:
    response = client.put(
        "/api/wedding-plan",
        json={"weddingDate": "2027-05-15", "availableAsset": -1},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"]["fields"]


def test_unknown_path_uses_common_not_found_error() -> None:
    response = client.get("/api/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "요청한 리소스를 찾을 수 없습니다.",
            "details": {},
        }
    }
