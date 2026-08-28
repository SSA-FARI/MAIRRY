import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AnalysisSource, DocumentStatus
from app.domains.documents.models import Document
from app.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)

_EXTRACTION_RAW = {
    "documentType": "WEDDING_HALL",
    "company": "A웨딩홀",
    "totalPrice": 23000000,
    "payments": [
        {
            "name": "잔금",
            "amount": 20000000,
            "dueDate": "2027-04-30",
            "status": "UNPAID",
            "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지",
        }
    ],
    "cancellationTerms": [],
    "warnings": [],
}


@contextmanager
def _document(
    status: DocumentStatus,
    *,
    wedding_plan_id: uuid.UUID | None = None,
    extraction_raw: dict | None = None,
    analysis_source: AnalysisSource = AnalysisSource.LIVE_AI,
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
                file_url=f"documents/{document_id}.pdf",
                content_type="application/pdf",
                analysis_status=status,
                analysis_source=analysis_source,
                extraction_raw=extraction_raw,
            )
        )
        session.commit()
        yield document_id
    finally:
        session.query(Document).filter(Document.id == document_id).delete()
        session.commit()
        session.close()


def test_get_document_returns_uploaded_status_without_extraction() -> None:
    with _document(DocumentStatus.UPLOADED) as document_id:
        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "UPLOADED"
        assert payload["analysisSource"] is None
        assert payload["extraction"] is None
        assert payload["error"] is None


def test_get_document_returns_extraction_when_review_required() -> None:
    with _document(
        DocumentStatus.REVIEW_REQUIRED,
        extraction_raw=_EXTRACTION_RAW,
        analysis_source=AnalysisSource.DEMO_FALLBACK,
    ) as document_id:
        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "REVIEW_REQUIRED"
        assert payload["analysisSource"] == "DEMO_FALLBACK"
        assert payload["extraction"]["company"] == "A웨딩홀"
        assert payload["extraction"]["payments"][0]["amount"] == 20000000


def test_get_document_returns_extraction_when_confirmed() -> None:
    with _document(
        DocumentStatus.CONFIRMED,
        extraction_raw=_EXTRACTION_RAW,
        analysis_source=AnalysisSource.LIVE_AI,
    ) as document_id:
        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "CONFIRMED"
        assert payload["analysisSource"] == "LIVE_AI"
        assert payload["extraction"]["documentType"] == "WEDDING_HALL"


def test_get_document_returns_404_when_missing() -> None:
    response = client.get(f"/api/documents/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_get_document_returns_404_for_other_wedding_plan() -> None:
    with _document(DocumentStatus.UPLOADED, wedding_plan_id=uuid.uuid4()) as document_id:
        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_get_document_returns_400_for_invalid_id_format() -> None:
    response = client.get("/api/documents/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
