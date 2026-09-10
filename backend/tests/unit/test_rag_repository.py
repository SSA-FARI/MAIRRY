from uuid import UUID

from sqlalchemy.dialects import postgresql

from ai.rag.schemas import KnowledgeType
from app.domains.rag.repository import RagRepository


class EmptyRows:
    def all(self):
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return EmptyRows()

    def scalars(self, _statement):
        raise AssertionError("Vector search must not materialize all ORM rows with scalars().all()")


def test_contract_search_requires_a_confirmed_contract_linked_to_the_same_plan_and_document() -> None:
    session = CapturingSession()
    plan_id = UUID(int=1)

    results = RagRepository(session).search(  # type: ignore[arg-type]
        [0.0] * 1536,
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
    assert "document_chunks.contract_id IS NOT NULL" in sql
    assert "document_chunks.document_id IS NOT NULL" in sql
    assert "contracts.status" in sql
    assert "contracts.wedding_plan_id" in sql
    assert "contracts.document_id = document_chunks.document_id" in sql
    assert "document_chunks.active IS true" in sql
    assert "document_chunks.embedding_vector IS NOT NULL" in sql
    assert "<=>" in sql
    assert "ORDER BY" in sql
    assert "LIMIT" in sql
    assert plan_id in compiled.params.values()


def test_global_knowledge_search_requires_null_plan_and_contract_scope() -> None:
    session = CapturingSession()

    RagRepository(session).search(  # type: ignore[arg-type]
        [0.0] * 1536,
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


def test_search_rejects_incompatible_query_dimension_before_sql() -> None:
    session = CapturingSession()

    try:
        RagRepository(session).search(  # type: ignore[arg-type]
            [0.0] * 384,
            knowledge_types={KnowledgeType.DOMAIN_KNOWLEDGE},
            wedding_plan_id=UUID(int=1),
            top_k=5,
            threshold=0.1,
            embedding_model="text-embedding-3-small",
            embedding_version="v1",
            embedding_dimensions=1536,
        )
    except ValueError as exc:
        assert "dimension" in str(exc).lower()
    else:
        raise AssertionError("Expected a dimension mismatch to be rejected")

    assert session.statement is None
