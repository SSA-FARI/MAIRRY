from uuid import UUID

from sqlalchemy.dialects import postgresql

from ai.rag.schemas import KnowledgeType
from app.domains.rag.repository import RagRepository


class EmptyScalars:
    def all(self):
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return EmptyScalars()


def test_contract_search_applies_plan_status_and_active_filters_in_sql() -> None:
    session = CapturingSession()
    plan_id = UUID(int=1)

    results = RagRepository(session).search(  # type: ignore[arg-type]
        [0.0] * 384,
        knowledge_types={KnowledgeType.CONTRACT_CLAUSE},
        wedding_plan_id=plan_id,
        top_k=5,
        threshold=0.1,
        embedding_model="text-embedding-3-small",
        embedding_version="v1",
        embedding_dimensions=1536,
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert results == []
    assert "document_chunks.wedding_plan_id" in sql
    assert "contracts.status" in sql
    assert "document_chunks.active IS true" in sql
    assert plan_id in compiled.params.values()


def test_global_knowledge_search_requires_null_plan_and_contract_scope() -> None:
    session = CapturingSession()

    RagRepository(session).search(  # type: ignore[arg-type]
        [0.0] * 384,
        knowledge_types={KnowledgeType.SERVICE_FAQ},
        wedding_plan_id=UUID(int=1),
        top_k=5,
        threshold=0.1,
        embedding_model="text-embedding-3-small",
        embedding_version="v1",
        embedding_dimensions=1536,
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "document_chunks.wedding_plan_id IS NULL" in sql
    assert "document_chunks.contract_id IS NULL" in sql


def test_search_filters_out_vectors_from_other_embedding_profiles() -> None:
    session = CapturingSession()

    RagRepository(session).search(  # type: ignore[arg-type]
        [0.0] * 1536,
        knowledge_types={KnowledgeType.DOMAIN_KNOWLEDGE},
        wedding_plan_id=UUID(int=1),
        top_k=5,
        threshold=0.1,
        embedding_model="text-embedding-3-small",
        embedding_version="v1",
        embedding_dimensions=1536,
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert "document_chunks.embedding_model" in str(compiled)
    assert "text-embedding-3-small" in compiled.params.values()
    assert 1536 in compiled.params.values()
