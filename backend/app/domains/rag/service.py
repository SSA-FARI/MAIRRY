import logging
from uuid import UUID

from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai.rag.chunking import ClauseSource, chunk_clause_sources
from ai.rag.document_text import extract_pdf_clause_sources
from ai.rag.embeddings import EmbeddingClient, OpenAiEmbeddingClient
from ai.rag.routing import contains_prompt_injection
from ai.rag.schemas import KnowledgeType, RetrievedChunk
from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.domains.contracts.models import Contract
from app.domains.documents.models import Document
from app.domains.rag.models import DocumentChunk
from app.domains.rag.repository import RagRepository
from app.integrations.storage.document_storage import MinioDocumentStorage

logger = logging.getLogger(__name__)


class ContractIndexingService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self._session = session
        self._configuration = configuration
        self._repository = RagRepository(session)
        self._embedder = embedding_client or build_embedding_client(configuration)

    def enqueue(self, contract_id: UUID, document_version: int) -> None:
        self._repository.enqueue(contract_id, document_version)

    def process(self, contract_id: UUID) -> None:
        job = self._repository.get_pending_job(contract_id)
        if job is None:
            return
        job.status = "INDEXING"
        job.attempts += 1
        self._session.flush()
        contract = self._session.scalar(
            select(Contract)
            .where(Contract.id == contract_id)
            .options(selectinload(Contract.payments), selectinload(Contract.cancellation_terms))
        )
        if contract is None:
            return
        sources = [
            ClauseSource(
                title=f"{contract.company} 계약서",
                clause_title="취소·환불 조건",
                content="\n".join(filter(None, [term.summary, term.source_text])),
            )
            for term in contract.cancellation_terms
        ]
        sources.extend(
            ClauseSource(
                title=f"{contract.company} 계약서",
                clause_title=payment.name,
                content=payment.source_text,
            )
            for payment in contract.payments
            if payment.source_text
        )
        document = self._session.get(Document, contract.document_id)
        if document is not None and document.content_type == "application/pdf":
            try:
                original = MinioDocumentStorage().read(document.file_url)
                sources.extend(extract_pdf_clause_sources(original))
            except (AppError, OSError, PdfReadError, ValueError) as exc:
                logger.warning(
                    "RAG original text unavailable: documentId=%s errorType=%s",
                    document.id,
                    type(exc).__name__,
                )
        chunks = chunk_clause_sources(
            sources,
            knowledge_type=KnowledgeType.CONTRACT_CLAUSE,
            namespace=f"contract:{contract.id}:v{job.document_version}",
            chunk_size=self._configuration.rag_chunk_size,
            overlap=self._configuration.rag_chunk_overlap,
        )
        embeddings = self._embedder.embed_many(chunk.content for chunk in chunks)
        models = [
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                content_hash=chunk.content_hash,
                knowledge_type=chunk.knowledge_type.value,
                wedding_plan_id=contract.wedding_plan_id,
                document_id=contract.document_id,
                contract_id=contract.id,
                title=chunk.title,
                clause_title=chunk.clause_title,
                page_number=chunk.page,
                chunk_index=chunk.chunk_index,
                document_version=job.document_version,
                content=chunk.content,
                embedding=embedding,
                embedding_model=self._embedder.model_name,
                embedding_version=self._embedder.version,
                embedding_dimensions=self._embedder.dimensions,
                active=True,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self._repository.replace_contract_chunks(contract.id, job.document_version, models)
        job.status = "INDEXED"
        job.error_code = None


def process_contract_index(contract_id: UUID, configuration: Settings) -> None:
    session = SessionLocal()
    try:
        ContractIndexingService(session, configuration).process(contract_id)
        session.commit()
    except Exception:
        session.rollback()
        job = RagRepository(session).get_pending_job(contract_id)
        if job is not None:
            job.status = "FAILED"
            job.error_code = "INDEXING_FAILED"
            session.commit()
        logger.exception("RAG contract indexing failed: contractId=%s", contract_id)
    finally:
        session.close()


class RagSearchService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self._repository = RagRepository(session)
        self._configuration = configuration
        self._embedder = embedding_client or build_embedding_client(configuration)

    def search(
        self,
        queries: list[str],
        *,
        knowledge_types: set[KnowledgeType],
        wedding_plan_id: UUID | None,
    ) -> list[RetrievedChunk]:
        if not self._configuration.rag_enabled:
            return []
        best_by_id: dict[str, RetrievedChunk] = {}
        selected_queries = queries[:3]
        query_embeddings = self._embedder.embed_many(selected_queries)
        for query_embedding in query_embeddings:
            results = self._repository.search(
                query_embedding,
                knowledge_types=knowledge_types,
                wedding_plan_id=wedding_plan_id,
                top_k=self._configuration.rag_search_top_k,
                threshold=self._configuration.rag_score_threshold,
                embedding_model=self._embedder.model_name,
                embedding_version=self._embedder.version,
                embedding_dimensions=self._embedder.dimensions,
            )
            for result in results:
                current = best_by_id.get(result.chunk_id)
                if current is None or result.score > current.score:
                    best_by_id[result.chunk_id] = result
        safe_chunks = [
            chunk for chunk in best_by_id.values() if not contains_prompt_injection(chunk.content)
        ]
        priority = {
            KnowledgeType.CONTRACT_CLAUSE: 3,
            KnowledgeType.SERVICE_FAQ: 2,
            KnowledgeType.DOMAIN_KNOWLEDGE: 1,
            KnowledgeType.CURATED_QA: 0,
        }
        return sorted(
            safe_chunks,
            key=lambda item: (priority[item.knowledge_type], item.score),
            reverse=True,
        )[: self._configuration.rag_max_context_chunks]


def build_embedding_client(configuration: Settings) -> OpenAiEmbeddingClient:
    return OpenAiEmbeddingClient(
        api_key=getattr(configuration, "ai_api_key", ""),
        base_url=getattr(configuration, "ai_base_url", "https://api.openai.com/v1"),
        model_name=getattr(configuration, "embedding_model_name", "text-embedding-3-small"),
        version=getattr(configuration, "embedding_version", "v1"),
        dimensions=getattr(configuration, "embedding_dimensions", 1536),
        timeout_seconds=getattr(configuration, "ai_timeout_seconds", 45),
        batch_size=getattr(configuration, "embedding_batch_size", 64),
    )
