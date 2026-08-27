import uuid

import pytest

from app.core.database import SessionLocal
from app.core.enums import AnalysisSource, DocumentStatus
from app.domains.documents.models import Document

pytestmark = pytest.mark.integration


def test_document_persists_and_reloads_enum_and_jsonb_fields() -> None:
    document_id = uuid.uuid4()
    extraction_raw = {
        "documentType": "WEDDING_HALL",
        "company": "그랜드웨딩홀",
        "totalPrice": 23000000,
        "payments": [],
        "cancellationTerms": [],
        "warnings": [],
    }

    session = SessionLocal()
    try:
        session.add(
            Document(
                id=document_id,
                wedding_plan_id=uuid.uuid4(),
                uploaded_by_member_id=uuid.uuid4(),
                original_filename="contract.pdf",
                file_url="documents/contract.pdf",
                content_type="application/pdf",
                extraction_raw=extraction_raw,
                analysis_status=DocumentStatus.REVIEW_REQUIRED,
                analysis_source=AnalysisSource.DEMO_FALLBACK,
            )
        )
        session.commit()

        session.expire_all()
        loaded = session.get(Document, document_id)

        assert loaded is not None
        assert loaded.analysis_status is DocumentStatus.REVIEW_REQUIRED
        assert loaded.analysis_source is AnalysisSource.DEMO_FALLBACK
        assert loaded.extraction_raw == extraction_raw
        assert loaded.created_at is not None
        assert loaded.updated_at is not None
    finally:
        session.rollback()
        session.query(Document).filter(Document.id == document_id).delete()
        session.commit()
        session.close()


def test_document_defaults_status_to_uploaded_and_source_to_live_ai() -> None:
    document_id = uuid.uuid4()

    session = SessionLocal()
    try:
        session.add(
            Document(
                id=document_id,
                wedding_plan_id=uuid.uuid4(),
                uploaded_by_member_id=uuid.uuid4(),
                original_filename="contract.pdf",
                file_url="documents/contract.pdf",
            )
        )
        session.commit()

        session.expire_all()
        loaded = session.get(Document, document_id)

        assert loaded is not None
        assert loaded.analysis_status is DocumentStatus.UPLOADED
        assert loaded.analysis_source is AnalysisSource.LIVE_AI
        assert loaded.extraction_raw is None
    finally:
        session.rollback()
        session.query(Document).filter(Document.id == document_id).delete()
        session.commit()
        session.close()
