import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

import httpx
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ai.rag.chunking import ClauseSource, chunk_clause_sources
from ai.rag.document_text import extract_pdf_clause_sources
from ai.rag.embeddings import (
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    EmbeddingClient,
    EmbeddingError,
    OpenAiEmbeddingClient,
)
from ai.rag.routing import contains_prompt_injection, is_relevant_contract_chunk
from ai.rag.schemas import KnowledgeType, RetrievedChunk
from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.domains.contracts.models import Contract
from app.domains.documents.models import Document
from app.domains.rag.models import DocumentChunk, RagIndexJob, RagIndexJobStatus
from app.domains.rag.repository import RagRepository
from app.integrations.storage.document_storage import MinioDocumentStorage

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
_embedding_http_clients: dict[float, httpx.Client] = {}
_embedding_http_clients_lock = Lock()


@dataclass(frozen=True)
class ClaimedIndexJob:
    id: UUID
    contract_id: UUID
    document_version: int
    attempt: int
    locked_at: datetime


@dataclass(frozen=True)
class ContractIndexSource:
    wedding_plan_id: UUID
    document_id: UUID
    clauses: tuple[ClauseSource, ...]
    file_url: str | None
    content_type: str | None


class ContractNotFoundForIndexing(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _claim_job(
    configuration: Settings,
    *,
    contract_id: UUID | None,
    session_factory: SessionFactory,
    now: datetime,
) -> ClaimedIndexJob | None:
    session = session_factory()
    try:
        job = RagRepository(session).claim_retryable_job(
            now=now,
            stale_before=now - timedelta(seconds=configuration.rag_index_stale_after_seconds),
            max_attempts=configuration.rag_index_max_attempts,
            contract_id=contract_id,
        )
        if job is None:
            session.rollback()
            return None
        claimed = ClaimedIndexJob(
            id=job.id,
            contract_id=job.contract_id,
            document_version=job.document_version,
            attempt=job.attempts,
            locked_at=now,
        )
        session.commit()
        return claimed
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _load_contract_source(
    claimed: ClaimedIndexJob,
    *,
    session_factory: SessionFactory,
) -> ContractIndexSource:
    session = session_factory()
    try:
        contract = session.scalar(
            select(Contract)
            .where(Contract.id == claimed.contract_id)
            .options(selectinload(Contract.payments), selectinload(Contract.cancellation_terms))
        )
        if contract is None:
            raise ContractNotFoundForIndexing("Contract no longer exists")
        clauses = [
            ClauseSource(
                title=f"{contract.company} 계약서",
                clause_title="취소·환불 조건",
                content="\n".join(filter(None, [term.summary, term.source_text])),
            )
            for term in contract.cancellation_terms
        ]
        clauses.extend(
            ClauseSource(
                title=f"{contract.company} 계약서",
                clause_title=payment.name,
                content=payment.source_text,
            )
            for payment in contract.payments
            if payment.source_text
        )
        document = session.get(Document, contract.document_id)
        return ContractIndexSource(
            wedding_plan_id=contract.wedding_plan_id,
            document_id=contract.document_id,
            clauses=tuple(clauses),
            file_url=document.file_url if document is not None else None,
            content_type=document.content_type if document is not None else None,
        )
    finally:
        session.close()


def _build_index_models(
    claimed: ClaimedIndexJob,
    source: ContractIndexSource,
    configuration: Settings,
    embedder: EmbeddingClient,
) -> list[DocumentChunk]:
    clauses = list(source.clauses)
    if source.content_type == "application/pdf" and source.file_url is not None:
        try:
            original = MinioDocumentStorage().read(source.file_url)
            clauses.extend(extract_pdf_clause_sources(original))
        except (AppError, OSError, PdfReadError, ValueError) as exc:
            logger.warning(
                "RAG original text unavailable: documentId=%s errorType=%s",
                source.document_id,
                type(exc).__name__,
            )
    chunks = chunk_clause_sources(
        clauses,
        knowledge_type=KnowledgeType.CONTRACT_CLAUSE,
        namespace=f"contract:{claimed.contract_id}:v{claimed.document_version}",
        chunk_size=configuration.rag_chunk_size,
        overlap=configuration.rag_chunk_overlap,
    )
    embeddings = embedder.embed_many(chunk.content for chunk in chunks)
    return [
        DocumentChunk(
            chunk_id=chunk.chunk_id,
            content_hash=chunk.content_hash,
            knowledge_type=chunk.knowledge_type.value,
            wedding_plan_id=source.wedding_plan_id,
            document_id=source.document_id,
            contract_id=claimed.contract_id,
            title=chunk.title,
            clause_title=chunk.clause_title,
            page_number=chunk.page,
            chunk_index=chunk.chunk_index,
            document_version=claimed.document_version,
            content=chunk.content,
            embedding=embedding,
            embedding_vector=embedding,
            embedding_model=embedder.model_name,
            embedding_version=embedder.version,
            embedding_dimensions=embedder.dimensions,
            active=True,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]


def _claim_is_current(job: RagIndexJob | None, claimed: ClaimedIndexJob) -> bool:
    return bool(
        job is not None
        and job.status == RagIndexJobStatus.INDEXING.value
        and job.attempts == claimed.attempt
        and job.locked_at == claimed.locked_at
    )


def _complete_job(
    claimed: ClaimedIndexJob,
    chunks: list[DocumentChunk],
    *,
    session_factory: SessionFactory,
) -> None:
    session = session_factory()
    try:
        job = session.scalar(
            select(RagIndexJob).where(RagIndexJob.id == claimed.id).with_for_update()
        )
        if not _claim_is_current(job, claimed):
            session.rollback()
            return
        RagRepository(session).replace_contract_chunks(
            claimed.contract_id, claimed.document_version, chunks
        )
        job.status = RagIndexJobStatus.INDEXED.value
        job.error_code = None
        job.locked_at = None
        job.next_attempt_at = None
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, ContractNotFoundForIndexing):
        return "CONTRACT_NOT_FOUND"
    if isinstance(exc, EmbeddingError):
        return "EMBEDDING_ERROR"
    if isinstance(exc, SQLAlchemyError):
        return "DATABASE_ERROR"
    return "INDEXING_FAILED"


def _record_failure(
    claimed: ClaimedIndexJob,
    exc: Exception,
    configuration: Settings,
    *,
    session_factory: SessionFactory,
    now: datetime,
) -> None:
    session = session_factory()
    try:
        job = session.scalar(
            select(RagIndexJob).where(RagIndexJob.id == claimed.id).with_for_update()
        )
        if not _claim_is_current(job, claimed):
            session.rollback()
            return
        job.status = RagIndexJobStatus.FAILED.value
        job.error_code = _failure_code(exc)
        job.locked_at = None
        if isinstance(exc, ContractNotFoundForIndexing):
            job.attempts = configuration.rag_index_max_attempts
            job.next_attempt_at = None
        else:
            delay = configuration.rag_index_retry_base_seconds * (2 ** (job.attempts - 1))
            job.next_attempt_at = now + timedelta(seconds=delay)
        session.commit()
    except Exception as record_exc:
        session.rollback()
        logger.error(
            "RAG index failure state could not be persisted: jobId=%s contractId=%s errorType=%s",
            claimed.id,
            claimed.contract_id,
            type(record_exc).__name__,
        )
        raise
    finally:
        session.close()


def process_next_index_job(
    configuration: Settings,
    *,
    contract_id: UUID | None = None,
    session_factory: SessionFactory = SessionLocal,
    embedding_client: EmbeddingClient | None = None,
    now_factory: Callable[[], datetime] = _utcnow,
) -> bool:
    claimed = _claim_job(
        configuration,
        contract_id=contract_id,
        session_factory=session_factory,
        now=now_factory(),
    )
    if claimed is None:
        return False
    try:
        source = _load_contract_source(claimed, session_factory=session_factory)
        embedder = embedding_client or build_embedding_client(configuration)
        chunks = _build_index_models(claimed, source, configuration, embedder)
        _complete_job(claimed, chunks, session_factory=session_factory)
    except Exception as exc:  # noqa: BLE001 - every indexing failure must release or expire its lease
        try:
            _record_failure(
                claimed,
                exc,
                configuration,
                session_factory=session_factory,
                now=now_factory(),
            )
        except Exception as failure_exc:  # noqa: BLE001
            # The stale lease is the durable recovery signal if the database is unavailable.
            logger.error(
                "RAG index failure state remains leased: jobId=%s errorType=%s",
                claimed.id,
                type(failure_exc).__name__,
            )
        logger.error(
            "RAG contract indexing failed: jobId=%s contractId=%s errorType=%s",
            claimed.id,
            claimed.contract_id,
            type(exc).__name__,
        )
    return True


def process_contract_index(contract_id: UUID, configuration: Settings) -> None:
    process_next_index_job(configuration, contract_id=contract_id)


def reconcile_index_jobs(configuration: Settings, *, limit: int | None = None) -> int:
    processed = 0
    for _ in range(limit or configuration.rag_index_batch_size):
        if not process_next_index_job(configuration):
            break
        processed += 1
    return processed


def _get_embedding_http_client(timeout_seconds: float) -> httpx.Client:
    with _embedding_http_clients_lock:
        client = _embedding_http_clients.get(timeout_seconds)
        if client is None or client.is_closed:
            client = httpx.Client(
                timeout=timeout_seconds,
                limits=httpx.Limits(
                    max_connections=DEFAULT_MAX_CONNECTIONS,
                    max_keepalive_connections=DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
                ),
            )
            _embedding_http_clients[timeout_seconds] = client
        return client


def close_embedding_http_clients() -> None:
    with _embedding_http_clients_lock:
        clients = tuple(_embedding_http_clients.values())
        _embedding_http_clients.clear()
    for client in clients:
        client.close()


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
        contract_id: UUID | None = None,
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
                contract_id=contract_id,
            )
            for result in results:
                current = best_by_id.get(result.chunk_id)
                if current is None or result.score > current.score:
                    best_by_id[result.chunk_id] = result
        combined_query = " ".join(selected_queries)
        safe_chunks = [
            chunk
            for chunk in best_by_id.values()
            if not contains_prompt_injection(chunk.content)
            and (
                chunk.knowledge_type != KnowledgeType.CONTRACT_CLAUSE
                or is_relevant_contract_chunk(combined_query, chunk.content)
            )
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
        http_client=_get_embedding_http_client(getattr(configuration, "ai_timeout_seconds", 45)),
    )
