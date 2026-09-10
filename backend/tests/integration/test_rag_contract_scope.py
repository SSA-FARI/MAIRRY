import hashlib
import uuid

import pytest

from ai.rag.schemas import KnowledgeType
from app.core.database import SessionLocal
from app.core.enums import ContractStatus, DocumentType
from app.domains.contracts.models import Contract
from app.domains.documents.models import Document
from app.domains.rag.models import DocumentChunk
from app.domains.rag.repository import RagRepository
from app.domains.wedding_plan.models import WeddingPlan

pytestmark = pytest.mark.integration

EMBEDDING_DIMENSIONS = 1536
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_VERSION = "v1"


def _chunk(
    *,
    label: str,
    wedding_plan_id: uuid.UUID,
    document_id: uuid.UUID | None,
    contract_id: uuid.UUID | None,
) -> DocumentChunk:
    content = f"{label} cancellation clause"
    embedding = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
    return DocumentChunk(
        chunk_id=f"contract-scope-{uuid.uuid4()}",
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        knowledge_type=KnowledgeType.CONTRACT_CLAUSE.value,
        wedding_plan_id=wedding_plan_id,
        document_id=document_id,
        contract_id=contract_id,
        title=label,
        clause_title="cancellation",
        page_number=1,
        chunk_index=0,
        document_version=1,
        content=content,
        embedding=embedding,
        embedding_vector=embedding,
        embedding_model=EMBEDDING_MODEL,
        embedding_version=EMBEDDING_VERSION,
        embedding_dimensions=EMBEDDING_DIMENSIONS,
        active=True,
    )


def test_contract_search_excludes_seed_and_other_plan_chunks() -> None:
    current_plan = WeddingPlan(id=uuid.uuid4())
    other_plan = WeddingPlan(id=uuid.uuid4())
    current_document = Document(
        id=uuid.uuid4(),
        wedding_plan_id=current_plan.id,
        uploaded_by_member_id=uuid.uuid4(),
        document_type=DocumentType.WEDDING_HALL.value,
        original_filename="current.pdf",
        file_url="documents/current.pdf",
    )
    other_document = Document(
        id=uuid.uuid4(),
        wedding_plan_id=other_plan.id,
        uploaded_by_member_id=uuid.uuid4(),
        document_type=DocumentType.WEDDING_HALL.value,
        original_filename="other.pdf",
        file_url="documents/other.pdf",
    )
    current_contract = Contract(
        id=uuid.uuid4(),
        wedding_plan_id=current_plan.id,
        document_id=current_document.id,
        document_type=DocumentType.WEDDING_HALL,
        company="Current vendor",
        total_price=1_000_000,
        status=ContractStatus.CONFIRMED,
    )
    other_contract = Contract(
        id=uuid.uuid4(),
        wedding_plan_id=other_plan.id,
        document_id=other_document.id,
        document_type=DocumentType.WEDDING_HALL,
        company="Other vendor",
        total_price=1_000_000,
        status=ContractStatus.CONFIRMED,
    )
    current_chunk = _chunk(
        label="current contract",
        wedding_plan_id=current_plan.id,
        document_id=current_document.id,
        contract_id=current_contract.id,
    )
    seed_chunk = _chunk(
        label="unlinked demo seed",
        wedding_plan_id=current_plan.id,
        document_id=None,
        contract_id=None,
    )
    other_chunk = _chunk(
        label="other plan contract",
        wedding_plan_id=other_plan.id,
        document_id=other_document.id,
        contract_id=other_contract.id,
    )

    session = SessionLocal()
    try:
        session.add_all([current_plan, other_plan])
        session.flush()
        session.add_all([current_document, other_document])
        session.flush()
        session.add_all([current_contract, other_contract])
        session.flush()
        session.add_all([current_chunk, seed_chunk, other_chunk])
        session.flush()

        results = RagRepository(session).search(
            [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
            knowledge_types={KnowledgeType.CONTRACT_CLAUSE},
            wedding_plan_id=current_plan.id,
            top_k=10,
            threshold=0.0,
            embedding_model=EMBEDDING_MODEL,
            embedding_version=EMBEDDING_VERSION,
            embedding_dimensions=EMBEDDING_DIMENSIONS,
        )

        assert [result.chunk_id for result in results] == [current_chunk.chunk_id]

        cross_plan_results = RagRepository(session).search(
            [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
            knowledge_types={KnowledgeType.CONTRACT_CLAUSE},
            wedding_plan_id=current_plan.id,
            contract_id=other_contract.id,
            top_k=10,
            threshold=0.0,
            embedding_model=EMBEDDING_MODEL,
            embedding_version=EMBEDDING_VERSION,
            embedding_dimensions=EMBEDDING_DIMENSIONS,
        )

        assert cross_plan_results == []
    finally:
        session.rollback()
        session.close()
