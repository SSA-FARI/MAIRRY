import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from ai.common.types import ToolResultView
from ai.rag.schemas import KnowledgeType, RetrievedChunk
from app.application.chat_orchestration import ChatOrchestrationService

PLAN_ID = UUID(int=10)
DOCUMENT_ID = UUID(int=11)
CONTRACT_ID = UUID(int=12)


class StubRagSearch:
    def __init__(self, chunks: list[RetrievedChunk] | None = None, error: Exception | None = None):
        self.chunks = chunks or []
        self.error = error
        self.calls: list[tuple[list[str], set[KnowledgeType], UUID | None]] = []

    def search(self, queries, *, knowledge_types, wedding_plan_id, contract_id=None):
        self.calls.append((queries, knowledge_types, wedding_plan_id))
        self.contract_id = contract_id
        if self.error:
            raise self.error
        return self.chunks


def _service(rag: StubRagSearch) -> ChatOrchestrationService:
    configuration = SimpleNamespace(
        demo_user_id=UUID(int=1),
        enable_demo_fallback=True,
        rag_history_limit=8,
    )
    return ChatOrchestrationService(
        SimpleNamespace(),
        configuration,
        rag_service=rag,  # type: ignore[arg-type]
        tool_registry=SimpleNamespace(),  # type: ignore[arg-type]
        plan_resolver=lambda _user_id: SimpleNamespace(id=PLAN_ID),
    )


def test_contract_clause_question_uses_rag_and_returns_matching_citation() -> None:
    rag = StubRagSearch(
        [
            RetrievedChunk(
                chunk_id="a" * 64,
                content_hash="b" * 64,
                content="예식 90일 전 취소 시 계약금을 환불합니다.",
                knowledge_type=KnowledgeType.CONTRACT_CLAUSE,
                title="A웨딩홀 계약서",
                clause_title="취소 규정",
                page=3,
                chunk_index=0,
                score=0.8,
                document_id=DOCUMENT_ID,
                contract_id=CONTRACT_ID,
            )
        ]
    )

    response = asyncio.run(_service(rag).process("이 계약을 취소하면 어떻게 돼?"))

    assert response.used_rag is True
    assert response.answer_type.value == "RAG"
    assert response.citations[0].document_id == DOCUMENT_ID
    assert response.citations[0].page == 3
    assert rag.calls[0][2] == PLAN_ID


def test_follow_up_question_is_rewritten_with_recent_context() -> None:
    rag = StubRagSearch()

    asyncio.run(
        _service(rag).process(
            "그럼 다음 달에 취소하면?",
            history=["A웨딩홀 계약의 취소 규정 알려줘"],
        )
    )

    assert "A웨딩홀" in rag.calls[0][0][0]


def test_retrieval_failure_does_not_fall_back_to_guessed_contract_terms() -> None:
    response = asyncio.run(
        _service(StubRagSearch(error=RuntimeError("private"))).process("환불 규정 알려줘")
    )

    assert response.answer_type.value == "NOT_FOUND"
    assert response.citations == []
    assert "private" not in response.answer


def test_mixed_follow_up_reuses_contract_for_payment_tool_and_rag_filter() -> None:
    rag = StubRagSearch(
        [
            RetrievedChunk(
                chunk_id="c" * 64,
                content_hash="d" * 64,
                content="예식 30일 전 취소 시 계약금은 반환되지 않습니다.",
                knowledge_type=KnowledgeType.CONTRACT_CLAUSE,
                title="라온벨 웨딩컨벤션 계약서",
                clause_title="취소 규정",
                page=2,
                chunk_index=0,
                score=0.9,
                document_id=DOCUMENT_ID,
                contract_id=CONTRACT_ID,
            )
        ]
    )

    class DepositRegistry:
        def __init__(self) -> None:
            self.calls = []

        def resolve_explicit_contract_id(self, _message, _user_id):
            return None

        def resolve_contract_id(self, _message, _user_id):
            return None

        def execute(self, tool_name, arguments, user_id):
            self.calls.append((tool_name, arguments, user_id))
            return ToolResultView(
                status="SUCCESS",
                tool_name="getContractDeposit",
                data={
                    "contractId": str(CONTRACT_ID),
                    "company": "라온벨 웨딩컨벤션",
                    "payment": {"amount": 3_000_000, "status": "PAID"},
                },
                evidence=[],
                calculated_at=datetime(2026, 9, 7, tzinfo=UTC),
                error=None,
            )

    registry = DepositRegistry()
    configuration = SimpleNamespace(
        demo_user_id=UUID(int=1),
        enable_demo_fallback=True,
        rag_history_limit=8,
    )
    service = ChatOrchestrationService(
        SimpleNamespace(),
        configuration,
        rag_service=rag,  # type: ignore[arg-type]
        tool_registry=registry,  # type: ignore[arg-type]
        plan_resolver=lambda _user_id: SimpleNamespace(id=PLAN_ID),
    )

    response = asyncio.run(
        service.process(
            "그 예약금은 지금 취소하면 어떻게 돼?",
            referenced_contract_id=CONTRACT_ID,
            referenced_document_id=DOCUMENT_ID,
            referenced_vendor_name="라온벨 웨딩컨벤션",
        )
    )

    assert registry.calls[0][0] == "getContractDeposit"
    assert registry.calls[0][1]["contractId"] == str(CONTRACT_ID)
    assert rag.contract_id == CONTRACT_ID
    assert service.contract_resolution_source == "conversation_context"
    assert response.answer_type.value == "MIXED"
    assert response.used_rag is True
