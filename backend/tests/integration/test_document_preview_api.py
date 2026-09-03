import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import DocumentStatus
from app.domains.documents.models import Document
from app.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)


@contextmanager
def _document(
    status: DocumentStatus = DocumentStatus.UPLOADED,
    *,
    wedding_plan_id: uuid.UUID | None = None,
) -> Iterator[uuid.UUID]:
    document_id = uuid.uuid4()
    session = SessionLocal()
    try:
        session.add(
            Document(
                id=document_id,
                wedding_plan_id=wedding_plan_id or settings.demo_wedding_plan_id,
                uploaded_by_member_id=settings.demo_member_id,
                original_filename="contract.pdf",
                file_url=f"{document_id}.pdf",
                content_type="application/pdf",
                analysis_status=status,
            )
        )
        session.commit()
        yield document_id
    finally:
        session.query(Document).filter(Document.id == document_id).delete()
        session.commit()
        session.close()


@pytest.mark.parametrize(
    "status",
    [
        DocumentStatus.UPLOADED,
        DocumentStatus.PROCESSING,
        DocumentStatus.REVIEW_REQUIRED,
        DocumentStatus.FAILED,
        DocumentStatus.CONFIRMED,
    ],
)
def test_get_preview_url_issues_signed_url_regardless_of_status(status: DocumentStatus) -> None:
    with _document(status) as document_id:
        response = client.get(f"/api/documents/{document_id}/preview-url")

        assert response.status_code == 200
        payload = response.json()
        assert payload["url"]
        # Every browser-reachable base is exposed as OBJECT_STORAGE_PUBLIC_ENDPOINT, never the
        # docker-compose-internal OBJECT_STORAGE_ENDPOINT host.
        assert payload["url"].startswith(settings.object_storage_public_endpoint)
        expires_at = datetime.fromisoformat(payload["expiresAt"])
        assert expires_at > datetime.now(expires_at.tzinfo)


def test_get_preview_url_returns_404_when_missing() -> None:
    response = client.get(f"/api/documents/{uuid.uuid4()}/preview-url")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_get_preview_url_returns_404_for_other_wedding_plan() -> None:
    with _document(wedding_plan_id=uuid.uuid4()) as document_id:
        response = client.get(f"/api/documents/{document_id}/preview-url")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_get_preview_url_returns_400_for_invalid_id_format() -> None:
    response = client.get("/api/documents/not-a-uuid/preview-url")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
