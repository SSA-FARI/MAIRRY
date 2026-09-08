from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeType(StrEnum):
    CONTRACT_CLAUSE = "CONTRACT_CLAUSE"
    SERVICE_FAQ = "SERVICE_FAQ"
    DOMAIN_KNOWLEDGE = "DOMAIN_KNOWLEDGE"
    CURATED_QA = "CURATED_QA"


class RagChunk(BaseModel):
    chunk_id: str
    content_hash: str
    content: str
    knowledge_type: KnowledgeType
    title: str
    clause_title: str | None = None
    page: int | None = Field(default=None, ge=1)
    chunk_index: int = Field(ge=0)


class RetrievedChunk(RagChunk):
    score: float = Field(ge=0, le=1)
    document_id: UUID | None = None
    contract_id: UUID | None = None
    document_version: int = Field(default=1, ge=1)
