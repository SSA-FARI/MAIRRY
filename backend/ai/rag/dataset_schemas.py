from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ai.rag.schemas import KnowledgeType


class KnowledgeScope(StrEnum):
    GLOBAL = "GLOBAL"
    DEMO_PLAN = "DEMO_PLAN"
    WEDDING_PLAN = "WEDDING_PLAN"


class RagDatasetRecord(BaseModel):
    id: str = Field(min_length=1, max_length=150)
    knowledge_type: KnowledgeType
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=100)
    scope: KnowledgeScope
    language: str = "ko"
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    version: int = Field(default=1, ge=1)
    clause_type: str | None = None
    demo_contract_key: str | None = None
    category: str | None = None
    vendor_name: str | None = None
    page: int | None = Field(default=None, ge=1)
    term: str | None = None
    question: str | None = None
    answer: str | None = None
    review_status: str | None = None

    @model_validator(mode="after")
    def validate_type_specific_fields(self) -> RagDatasetRecord:
        required: dict[KnowledgeType, tuple[str, ...]] = {
            KnowledgeType.CONTRACT_CLAUSE: ("clause_type", "demo_contract_key"),
            KnowledgeType.DOMAIN_KNOWLEDGE: ("term",),
            KnowledgeType.SERVICE_FAQ: ("question",),
            KnowledgeType.CURATED_QA: ("question", "answer", "review_status"),
        }
        missing = [name for name in required[self.knowledge_type] if not getattr(self, name)]
        if missing:
            raise ValueError(f"{self.knowledge_type.value} requires: {', '.join(missing)}")
        if self.knowledge_type == KnowledgeType.CONTRACT_CLAUSE:
            if self.scope != KnowledgeScope.DEMO_PLAN:
                raise ValueError("Seed contract clauses must use DEMO_PLAN scope")
        elif self.scope != KnowledgeScope.GLOBAL:
            raise ValueError("Public seed knowledge must use GLOBAL scope")
        return self


def build_embedding_text(record: RagDatasetRecord) -> str:
    aliases = ", ".join(record.aliases)
    tags = ", ".join(record.tags)
    if record.knowledge_type == KnowledgeType.CONTRACT_CLAUSE:
        return "\n".join(
            filter(
                None,
                [
                    "문서 유형: 계약서 조항",
                    f"계약 종류: {record.category}",
                    f"업체: {record.vendor_name}",
                    f"조항 유형: {record.clause_type}",
                    f"제목: {record.title}",
                    f"별칭: {tags}" if tags else None,
                    f"내용: {record.content}",
                ],
            )
        )
    if record.knowledge_type == KnowledgeType.DOMAIN_KNOWLEDGE:
        return "\n".join(
            filter(
                None,
                [
                    f"용어: {record.term}",
                    f"동의어: {aliases}" if aliases else None,
                    f"카테고리: {record.category}",
                    f"설명: {record.content}",
                ],
            )
        )
    if record.knowledge_type == KnowledgeType.SERVICE_FAQ:
        return "\n".join(
            filter(
                None,
                [
                    f"질문: {record.question}",
                    f"유사 질문: {aliases}" if aliases else None,
                    f"답변: {record.content}",
                ],
            )
        )
    return f"질문: {record.question}\n답변: {record.answer}"
