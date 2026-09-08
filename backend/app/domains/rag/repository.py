from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from ai.rag.embeddings import DEFAULT_EMBEDDING_DIMENSIONS
from ai.rag.schemas import KnowledgeType, RetrievedChunk
from app.core.enums import ContractStatus
from app.domains.contracts.models import Contract
from app.domains.rag.models import DocumentChunk, RagIndexJob, RagIndexJobStatus


class RagRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, contract_id: UUID, document_version: int) -> RagIndexJob:
        existing = self._session.scalar(
            select(RagIndexJob).where(
                RagIndexJob.contract_id == contract_id,
                RagIndexJob.document_version == document_version,
            )
        )
        if existing is not None:
            existing.status = RagIndexJobStatus.PENDING.value
            existing.attempts = 0
            existing.error_code = None
            existing.locked_at = None
            existing.next_attempt_at = None
            return existing
        job = RagIndexJob(contract_id=contract_id, document_version=document_version)
        self._session.add(job)
        return job

    def next_version(self, contract_id: UUID) -> int:
        latest = self._session.scalar(
            select(func.max(RagIndexJob.document_version)).where(
                RagIndexJob.contract_id == contract_id
            )
        )
        return int(latest or 0) + 1

    def claim_retryable_job(
        self,
        *,
        now: datetime,
        stale_before: datetime,
        max_attempts: int,
        contract_id: UUID | None = None,
    ) -> RagIndexJob | None:
        ready_to_retry = and_(
            RagIndexJob.status.in_(
                [RagIndexJobStatus.PENDING.value, RagIndexJobStatus.FAILED.value]
            ),
            or_(RagIndexJob.next_attempt_at.is_(None), RagIndexJob.next_attempt_at <= now),
        )
        stale_claim = and_(
            RagIndexJob.status == RagIndexJobStatus.INDEXING.value,
            or_(RagIndexJob.locked_at.is_(None), RagIndexJob.locked_at < stale_before),
        )
        statement = (
            select(RagIndexJob)
            .where(
                RagIndexJob.attempts < max_attempts,
                or_(ready_to_retry, stale_claim),
            )
            .order_by(RagIndexJob.created_at, RagIndexJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if contract_id is not None:
            statement = statement.where(RagIndexJob.contract_id == contract_id)
        job = self._session.scalar(statement)
        if job is None:
            return None
        job.status = RagIndexJobStatus.INDEXING.value
        job.attempts += 1
        job.error_code = None
        job.locked_at = now
        job.next_attempt_at = None
        self._session.flush()
        return job

    def replace_contract_chunks(
        self,
        contract_id: UUID,
        document_version: int,
        chunks: list[DocumentChunk],
    ) -> None:
        self._session.execute(
            update(DocumentChunk)
            .where(DocumentChunk.contract_id == contract_id)
            .values(active=False)
        )
        self._session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.contract_id == contract_id,
                DocumentChunk.document_version == document_version,
            )
        )
        self._session.add_all(chunks)

    def delete_contract_chunks(self, contract_id: UUID) -> None:
        self._session.execute(delete(DocumentChunk).where(DocumentChunk.contract_id == contract_id))

    def search(
        self,
        query_embedding: list[float],
        *,
        knowledge_types: set[KnowledgeType],
        wedding_plan_id: UUID | None,
        top_k: int,
        threshold: float,
        embedding_model: str,
        embedding_version: str,
        embedding_dimensions: int,
        contract_id: UUID | None = None,
    ) -> list[RetrievedChunk]:
        if not knowledge_types:
            return []
        if embedding_dimensions != DEFAULT_EMBEDDING_DIMENSIONS:
            raise ValueError(f"DB vector search requires {DEFAULT_EMBEDDING_DIMENSIONS} dimensions")
        if len(query_embedding) != embedding_dimensions:
            raise ValueError("Query embedding dimension does not match the configured profile")
        # Scope is applied in SQL before vectors or content leave persistence.
        global_types = knowledge_types - {KnowledgeType.CONTRACT_CLAUSE}
        scope_conditions = []
        if KnowledgeType.CONTRACT_CLAUSE in knowledge_types:
            scope_conditions.append(
                and_(
                    DocumentChunk.knowledge_type == KnowledgeType.CONTRACT_CLAUSE.value,
                    DocumentChunk.wedding_plan_id == wedding_plan_id,
                    or_(
                        Contract.status == ContractStatus.CONFIRMED,
                        DocumentChunk.contract_id.is_(None),
                    ),
                )
            )
        if global_types:
            scope_conditions.append(
                and_(
                    DocumentChunk.knowledge_type.in_([item.value for item in global_types]),
                    DocumentChunk.wedding_plan_id.is_(None),
                    DocumentChunk.contract_id.is_(None),
                )
            )
        distance = DocumentChunk.embedding_vector.cosine_distance(query_embedding)
        score = func.greatest(0.0, func.least(1.0, 1.0 - distance)).label("score")
        statement = (
            select(DocumentChunk, score)
            .outerjoin(Contract, DocumentChunk.contract_id == Contract.id)
            .where(
                DocumentChunk.active.is_(True),
                DocumentChunk.embedding_vector.is_not(None),
                DocumentChunk.embedding_model == embedding_model,
                DocumentChunk.embedding_version == embedding_version,
                DocumentChunk.embedding_dimensions == embedding_dimensions,
                or_(*scope_conditions),
                distance <= 1.0 - threshold,
            )
            .order_by(distance.asc(), DocumentChunk.id)
            .limit(top_k)
        )
        if contract_id is not None:
            statement = statement.where(DocumentChunk.contract_id == contract_id)
        rows = self._session.execute(statement).all()
        return [
            RetrievedChunk(
                chunk_id=row.chunk_id,
                content_hash=row.content_hash,
                content=row.content,
                knowledge_type=KnowledgeType(row.knowledge_type),
                title=row.title,
                clause_title=row.clause_title,
                page=row.page_number,
                chunk_index=row.chunk_index,
                score=float(score_value),
                document_id=row.document_id,
                contract_id=row.contract_id,
                document_version=row.document_version,
            )
            for row, score_value in rows
        ]
