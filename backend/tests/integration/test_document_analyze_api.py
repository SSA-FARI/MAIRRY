import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from ai.document_extraction.fallback import DEFAULT_DEMO_DOCUMENT_PATH
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import DocumentStatus
from app.domains.documents.models import Document
from app.integrations.storage.document_storage import _build_client
from app.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)

_DEMO_FALLBACK_CONTENT = DEFAULT_DEMO_DOCUMENT_PATH.read_bytes()
_UNKNOWN_CONTENT = b"this content does not match any registered demo fallback"


@contextmanager
def _stored_document(
    content: bytes, *, status: DocumentStatus = DocumentStatus.UPLOADED
) -> Iterator[uuid.UUID]:
    document_id = uuid.uuid4()
    storage_key = f"{document_id}.pdf"
    _build_client().put_object(
        Bucket=settings.object_storage_bucket,
        Key=storage_key,
        Body=content,
        ContentType="application/pdf",
    )
    session = SessionLocal()
    try:
        session.add(
            Document(
                id=document_id,
                wedding_plan_id=settings.demo_wedding_plan_id,
                uploaded_by_member_id=settings.demo_member_id,
                original_filename="contract.pdf",
                file_url=storage_key,
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
        try:
            _build_client().delete_object(Bucket=settings.object_storage_bucket, Key=storage_key)
        except ClientError:
            pass


def test_analyze_document_accepts_and_reports_processing_immediately() -> None:
    with _stored_document(_DEMO_FALLBACK_CONTENT) as document_id:
        response = client.post(f"/api/documents/{document_id}/analyze")

        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "PROCESSING"
        assert payload["analysisSource"] is None
        assert payload["extraction"] is None
        assert payload["error"] is None


def test_analyze_document_resolves_to_review_required_via_demo_fallback() -> None:
    with _stored_document(_DEMO_FALLBACK_CONTENT) as document_id:
        client.post(f"/api/documents/{document_id}/analyze")

        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "REVIEW_REQUIRED"
        assert payload["analysisSource"] == "DEMO_FALLBACK"
        assert payload["extraction"]["company"] == "A웨딩홀"
        assert payload["extraction"]["payments"][1]["amount"] == 20000000


def test_analyze_document_resolves_to_failed_when_no_fallback_matches() -> None:
    with _stored_document(_UNKNOWN_CONTENT) as document_id:
        client.post(f"/api/documents/{document_id}/analyze")

        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "FAILED"
        assert payload["analysisSource"] is None
        assert payload["extraction"] is None


def test_analyze_document_allows_retry_from_failed_status() -> None:
    with _stored_document(_UNKNOWN_CONTENT, status=DocumentStatus.FAILED) as document_id:
        response = client.post(f"/api/documents/{document_id}/analyze")

        assert response.status_code == 202
        assert response.json()["status"] == "PROCESSING"


@pytest.mark.parametrize(
    "status",
    [DocumentStatus.PROCESSING, DocumentStatus.REVIEW_REQUIRED, DocumentStatus.CONFIRMED],
)
def test_analyze_document_returns_409_for_disallowed_current_status(status: DocumentStatus) -> None:
    with _stored_document(_DEMO_FALLBACK_CONTENT, status=status) as document_id:
        response = client.post(f"/api/documents/{document_id}/analyze")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_STATE"


def test_analyze_document_returns_404_when_missing() -> None:
    response = client.post(f"/api/documents/{uuid.uuid4()}/analyze")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
