import uuid

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.domains.documents.models import Document
from app.integrations.storage.document_storage import _build_client
from app.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)

_PDF_CONTENT = b"%PDF-1.4\n%mock wedding hall contract for tests\n"


def _delete_document(document_id: str) -> None:
    session = SessionLocal()
    try:
        session.query(Document).filter(Document.id == uuid.UUID(document_id)).delete()
        session.commit()
    finally:
        session.close()

    try:
        _build_client().delete_object(
            Bucket=settings.object_storage_bucket, Key=f"{document_id}.pdf"
        )
    except ClientError:
        pass


def test_upload_pdf_creates_document_in_uploaded_status() -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("contract.pdf", _PDF_CONTENT, "application/pdf")},
    )

    try:
        assert response.status_code == 201
        payload = response.json()
        assert payload["originalName"] == "contract.pdf"
        assert payload["status"] == "UPLOADED"
        uuid.UUID(payload["id"])
    finally:
        if response.status_code == 201:
            _delete_document(response.json()["id"])


def test_upload_rejects_unsupported_extension() -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("contract.docx", b"not a real document", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_rejects_content_mismatching_extension() -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("contract.pdf", b"this is not actually a pdf", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_rejects_file_larger_than_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_upload_size_bytes", len(_PDF_CONTENT) - 1)

    response = client.post(
        "/api/documents",
        files={"file": ("contract.pdf", _PDF_CONTENT, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
