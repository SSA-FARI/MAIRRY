from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from ai.rag.embeddings import cosine_similarity
from ai.rag.schemas import KnowledgeType, RetrievedChunk
from app.core.enums import ContractStatus
from app.domains.contracts.models import Contract
from app.domains.rag.models import DocumentChunk, RagIndexJob


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
            existing.status = "PENDING"
            existing.error_code = None
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

    def get_pending_job(self, contract_id: UUID) -> RagIndexJob | None:
        return self._session.scalar(
            select(RagIndexJob)
            .where(
                RagIndexJob.contract_id == contract_id,
                RagIndexJob.status.in_(["PENDING", "FAILED"]),
            )
            .order_by(RagIndexJob.document_version.desc())
            .limit(1)
            .with_for_update()
        )

    def list_retryable_contract_ids(self, limit: int = 100) -> list[UUID]:
        return list(
            self._session.scalars(
                select(RagIndexJob.contract_id)
                .where(
                    RagIndexJob.status.in_(["PENDING", "FAILED"]),
                    RagIndexJob.attempts < 3,
                )
                .order_by(RagIndexJob.created_at)
                .limit(limit)
            ).all()
        )

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
    ) -> list[RetrievedChunk]:
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
        statement = (
            select(DocumentChunk)
            .outerjoin(Contract, DocumentChunk.contract_id == Contract.id)
            .where(
                DocumentChunk.active.is_(True),
                DocumentChunk.embedding_model == embedding_model,
                DocumentChunk.embedding_version == embedding_version,
                DocumentChunk.embedding_dimensions == embedding_dimensions,
                or_(*scope_conditions),
            )
        )
        rows = self._session.scalars(statement).all()
        ranked = sorted(
            ((row, cosine_similarity(query_embedding, row.embedding)) for row in rows),
            key=lambda item: item[1],
            reverse=True,
        )
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
                score=score,
                document_id=row.document_id,
                contract_id=row.contract_id,
                document_version=row.document_version,
            )
            for row, score in ranked[:top_k]
            if score >= threshold
        ]
