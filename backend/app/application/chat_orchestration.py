import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, NoReturn, TypedDict
from uuid import UUID

from fastapi import status
from langgraph.graph import END, START, StateGraph
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai.chat_agent.agent import decide_tool
from ai.chat_agent.fallback import IntentDecision, classify_message
from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.response import AnswerDraft, explain_tool_result
from ai.common.exceptions import AiError
from ai.common.types import ToolResultView
from ai.providers.base import ChatProvider
from ai.rag.routing import (
    RagRoute,
    classify_rag_route,
    expand_queries,
    has_contract_reference,
    rewrite_question,
)
from ai.rag.schemas import KnowledgeType, RetrievedChunk
from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.chat.schemas import ChatResponse
from app.domains.chat.tools import ChatToolRegistry
from app.domains.rag.service import RagSearchService
from app.domains.wedding_plan.repository import WeddingPlanRepository

IntentClassifier = Callable[[str], IntentDecision]
PlanResolver = Callable[[Any], Any]
logger = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    question: str
    history: list[str]
    rewritten_question: str
    queries: list[str]
    route: RagRoute
    knowledge_types: set[KnowledgeType]
    decision: IntentDecision
    tool_result: ToolResultView | None
    retrieved_chunks: list[RetrievedChunk]
    response: ChatResponse
    use_provider: bool
    retrieval_failed: bool
    referenced_contract_id: UUID | None
    referenced_document_id: UUID | None
    referenced_vendor_name: str | None


class ChatOrchestrationService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        classifier: IntentClassifier = classify_message,
        provider: ChatProvider | None = None,
        tool_registry: ChatToolRegistry | None = None,
        rag_service: RagSearchService | None = None,
        plan_resolver: PlanResolver | None = None,
    ) -> None:
        self._session = session
        self._configuration = configuration
        self._classifier = classifier
        self._provider = provider
        self._tools = tool_registry or ChatToolRegistry(session, configuration)
        self._rag = rag_service or RagSearchService(session, configuration)
        self._plan_resolver = (
            plan_resolver or WeddingPlanRepository(self._session).get_current_for_user
        )
        self._graph = self._build_graph()
        self.referenced_contract_id: UUID | None = None
        self.referenced_document_id: UUID | None = None
        self.referenced_vendor_name: str | None = None
        self.intent: str | None = None
        self.tool_name: str | None = None
        self.contract_resolution_source: str | None = None
        self.retrieved_chunk_count = 0

    async def process(
        self,
        message: str,
        *,
        history: list[str] | None = None,
        referenced_contract_id: UUID | None = None,
        referenced_document_id: UUID | None = None,
        referenced_vendor_name: str | None = None,
    ) -> ChatResponse:
        self.contract_resolution_source = None
        state = await self._graph.ainvoke(
            {
                "question": message,
                "history": (history or [])[-getattr(self._configuration, "rag_history_limit", 8) :],
                "referenced_contract_id": referenced_contract_id,
                "referenced_document_id": referenced_document_id,
                "referenced_vendor_name": referenced_vendor_name,
            }
        )
        self.referenced_contract_id = state.get("referenced_contract_id")
        self.referenced_document_id = state.get("referenced_document_id")
        self.referenced_vendor_name = state.get("referenced_vendor_name")
        decision = state.get("decision")
        self.intent = decision.intent.value if decision is not None else None
        tool_result = state.get("tool_result")
        self.tool_name = tool_result.tool_name if tool_result is not None else None
        self.retrieved_chunk_count = len(state.get("retrieved_chunks", []))
        return state["response"]

    def _build_graph(self):
        graph = StateGraph(ChatState)
        graph.add_node("prepare", self._prepare)
        graph.add_node("classify", self._classify)
        graph.add_node("tool", self._tool)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("generate", self._generate)
        graph.add_edge(START, "prepare")
        graph.add_edge("prepare", "classify")
        graph.add_conditional_edges(
            "classify",
            lambda state: state["route"].value,
            {
                RagRoute.TOOL.value: "tool",
                RagRoute.RAG.value: "retrieve",
                RagRoute.MIXED.value: "tool",
                RagRoute.GENERAL.value: "generate",
            },
        )
        graph.add_conditional_edges(
            "tool",
            lambda state: "retrieve" if state["route"] == RagRoute.MIXED else "generate",
            {"retrieve": "retrieve", "generate": "generate"},
        )
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    def _prepare(self, state: ChatState) -> dict[str, Any]:
        rewritten = rewrite_question(
            state["question"],
            state.get("history", []),
            state.get("referenced_vendor_name"),
        )
        return {"rewritten_question": rewritten, "queries": expand_queries(rewritten)}

    async def _classify(self, state: ChatState) -> dict[str, Any]:
        route, knowledge_types = classify_rag_route(state["rewritten_question"])
        decision = IntentDecision(ChatIntent.UNKNOWN, {})
        use_provider = False
        if route in {RagRoute.TOOL, RagRoute.MIXED}:
            decision, use_provider = await self._classify_intent(state["rewritten_question"])
            if decision.intent == ChatIntent.UNKNOWN and route == RagRoute.TOOL:
                route = RagRoute.GENERAL
        elif route == RagRoute.RAG:
            use_provider = self._provider is not None
        return {
            "route": route,
            "knowledge_types": knowledge_types,
            "decision": decision,
            "use_provider": use_provider,
        }

    async def _tool(self, state: ChatState) -> dict[str, Any]:
        result = await run_in_threadpool(
            self._execute_tool,
            state["rewritten_question"],
            state["decision"],
            state.get("referenced_contract_id"),
            has_contract_reference(state["question"]),
        )
        context = self._context_from_tool_result(result)
        return {"tool_result": result, **context}

    async def _retrieve(self, state: ChatState) -> dict[str, Any]:
        explicit_reference_context: dict[str, Any] = {}
        try:
            explicit_context_resolver = getattr(
                self._tools, "resolve_explicit_contract_context", None
            )
            explicit_context = (
                await run_in_threadpool(
                    explicit_context_resolver,
                    state["rewritten_question"],
                    self._configuration.demo_user_id,
                )
                if explicit_context_resolver is not None
                else None
            )
            target_contract_id = (
                UUID(explicit_context["contractId"])
                if explicit_context is not None
                else (
                    state.get("referenced_contract_id")
                    if has_contract_reference(state["question"])
                    else None
                )
            )
            if explicit_context is not None:
                self.contract_resolution_source = (
                    "conversation_context"
                    if has_contract_reference(state["question"])
                    and target_contract_id == state.get("referenced_contract_id")
                    else "explicit_vendor"
                )
                explicit_reference_context = {
                    "referenced_contract_id": target_contract_id,
                    "referenced_document_id": UUID(explicit_context["documentId"]),
                    "referenced_vendor_name": explicit_context["company"],
                }
            elif target_contract_id is not None:
                self.contract_resolution_source = "conversation_context"
            plan = await run_in_threadpool(
                self._plan_resolver,
                self._configuration.demo_user_id,
            )
            search_arguments = {
                "knowledge_types": state["knowledge_types"],
                "wedding_plan_id": plan.id if plan is not None else None,
            }
            if target_contract_id is not None:
                search_arguments["contract_id"] = target_contract_id
            chunks = await run_in_threadpool(
                self._rag.search,
                state["queries"],
                **search_arguments,
            )
            context = explicit_reference_context.copy()
            contract_chunk = next((chunk for chunk in chunks if chunk.contract_id), None)
            if contract_chunk is not None:
                vendor_name = contract_chunk.title.removesuffix(" 계약서").strip()
                context.update(
                    {
                        "referenced_contract_id": contract_chunk.contract_id,
                        "referenced_document_id": contract_chunk.document_id,
                        "referenced_vendor_name": context.get(
                            "referenced_vendor_name", vendor_name
                        ),
                    }
                )
            return {"retrieved_chunks": chunks, "retrieval_failed": False, **context}
        except (SQLAlchemyError, RuntimeError, ValueError) as exc:
            logger.warning("RAG retrieval failed: errorType=%s", type(exc).__name__)
            return {
                "retrieved_chunks": [],
                "retrieval_failed": True,
                **explicit_reference_context,
            }

    async def _generate(self, state: ChatState) -> dict[str, Any]:
        chunks = state.get("retrieved_chunks", [])
        tool_result = state.get("tool_result")
        if state["route"] == RagRoute.GENERAL:
            return {"response": self._unsupported_response()}
        tool_draft = explain_tool_result(state["question"], tool_result) if tool_result else None
        if not chunks:
            if state["route"] == RagRoute.RAG:
                return {"response": self._rag_unavailable_response()}
            if tool_draft is None:
                return {"response": self._unsupported_response()}
            tool_draft = await self._generate_tool_answer(
                state["question"], tool_result, tool_draft, use_provider=state["use_provider"]
            )
            return {"response": self._to_response(tool_draft)}

        citations = [self._citation(chunk) for chunk in chunks]
        evidence_summary = "\n\n".join(
            f"[{chunk.title}{' · ' + chunk.clause_title if chunk.clause_title else ''}]\n{chunk.content}"
            for chunk in chunks[:3]
        )
        grounded = "확인된 근거는 다음과 같습니다.\n" + evidence_summary
        if any(chunk.knowledge_type == KnowledgeType.CONTRACT_CLAUSE for chunk in chunks):
            grounded += "\n\n계약 조건은 원문과 업체에 최종 확인해 주세요."
        answer = f"{tool_draft.answer}\n\n{grounded}" if tool_draft else grounded
        if state["use_provider"] and self._provider is not None:
            answer = await self._generate_rag_answer(
                state["question"],
                chunks,
                tool_result,
                fallback=answer,
            )
        return {
            "response": ChatResponse.model_validate(
                {
                    "answer": answer,
                    "answerType": "MIXED" if tool_draft else "RAG",
                    "citations": citations,
                    "calculation": tool_draft.calculation if tool_draft else None,
                    "usedRag": True,
                }
            )
        }

    @staticmethod
    def _citation(chunk: RetrievedChunk) -> dict[str, Any]:
        return {
            "contractId": chunk.contract_id,
            "documentId": chunk.document_id,
            "sourceType": chunk.knowledge_type.value,
            "title": chunk.title,
            "clauseTitle": chunk.clause_title,
            "page": chunk.page,
            "label": " · ".join(filter(None, [chunk.title, chunk.clause_title])),
            "sourceText": chunk.content,
        }

    def _execute_tool(
        self,
        message: str,
        decision: IntentDecision,
        referenced_contract_id: UUID | None = None,
        references_previous_contract: bool = False,
    ) -> ToolResultView | None:
        arguments = dict(decision.arguments)
        self.contract_resolution_source = "provider_argument" if "contractId" in arguments else None
        if (
            decision.intent
            in {ChatIntent.CONTRACT, ChatIntent.CONTRACT_PAYMENT, ChatIntent.SCHEDULE}
            and "contractId" not in arguments
        ):
            explicit_resolver = getattr(self._tools, "resolve_explicit_contract_id", None)
            explicit_contract_id = (
                explicit_resolver(message, self._configuration.demo_user_id)
                if explicit_resolver is not None
                else None
            )
            contract_id = explicit_contract_id
            if explicit_contract_id is not None:
                self.contract_resolution_source = (
                    "conversation_context"
                    if references_previous_contract
                    and explicit_contract_id == referenced_contract_id
                    else "explicit_vendor"
                )
            if contract_id is None and referenced_contract_id and references_previous_contract:
                contract_id = referenced_contract_id
                self.contract_resolution_source = "conversation_context"
            if contract_id is None:
                contract_id = self._tools.resolve_contract_id(
                    message, self._configuration.demo_user_id
                )
                if contract_id is not None:
                    self.contract_resolution_source = "confirmed_contract_fallback"
            if contract_id is not None:
                arguments["contractId"] = str(contract_id)
        call = decide_tool(decision.intent, arguments)
        return (
            self._tools.execute(call.tool_name, call.arguments, self._configuration.demo_user_id)
            if call is not None
            else None
        )

    @staticmethod
    def _context_from_tool_result(result: ToolResultView | None) -> dict[str, Any]:
        if result is None or result.status != "SUCCESS" or result.data is None:
            return {}
        raw_contract_id = result.data.get("contractId") or result.data.get("id")
        if raw_contract_id is None:
            payments = result.data.get("payments", [])
            raw_contract_id = payments[0].get("contractId") if len(payments) == 1 else None
        try:
            contract_id = UUID(str(raw_contract_id)) if raw_contract_id else None
        except ValueError:
            contract_id = None
        context = {
            "referenced_contract_id": contract_id,
            "referenced_document_id": (
                UUID(str(result.data["documentId"])) if result.data.get("documentId") else None
            ),
            "referenced_vendor_name": result.data.get("company"),
        }
        return {key: value for key, value in context.items() if value is not None}

    async def _classify_intent(self, message: str) -> tuple[IntentDecision, bool]:
        if self._provider is None:
            if self._configuration.enable_demo_fallback:
                return self._classifier(message), False
            self._raise_provider_unavailable()
        try:
            return await self._provider.classify_intent(message), True
        except AiError as exc:
            self._log_provider_failure("intent", exc)
            if self._configuration.enable_demo_fallback:
                return self._classifier(message), False
            self._raise_provider_unavailable()

    async def _generate_tool_answer(
        self,
        message: str,
        result: ToolResultView,
        fallback_draft: AnswerDraft,
        *,
        use_provider: bool,
    ) -> AnswerDraft:
        if (
            not use_provider
            or self._provider is None
            or result.status != "SUCCESS"
            or result.data is None
        ):
            return fallback_draft
        try:
            answer = await self._provider.generate_answer(message, result)
        except AiError as exc:
            self._log_provider_failure("answer", exc)
            if self._configuration.enable_demo_fallback:
                return fallback_draft
            self._raise_provider_unavailable()
        return replace(fallback_draft, answer=answer)

    async def _generate_rag_answer(
        self,
        message: str,
        chunks: list[RetrievedChunk],
        tool_result: ToolResultView | None,
        *,
        fallback: str,
    ) -> str:
        data: dict[str, Any] = {
            "knowledge": [
                {
                    "sourceType": chunk.knowledge_type.value,
                    "title": chunk.title,
                    "clauseTitle": chunk.clause_title,
                    "content": chunk.content,
                }
                for chunk in chunks
            ]
        }
        if tool_result is not None and tool_result.status == "SUCCESS":
            data["authoritativeTool"] = {
                "toolName": tool_result.tool_name,
                "data": tool_result.data,
            }
        grounded_result = ToolResultView(
            status="SUCCESS",
            tool_name="searchKnowledge",
            data=data,
            evidence=[],
            calculated_at=(
                tool_result.calculated_at if tool_result is not None else datetime.now(UTC)
            ),
            error=None,
        )
        assert self._provider is not None
        try:
            return await self._provider.generate_answer(message, grounded_result)
        except AiError as exc:
            self._log_provider_failure("rag-answer", exc)
            return fallback

    @staticmethod
    def _log_provider_failure(stage: str, exc: AiError) -> None:
        logger.warning("Chat AI provider failed: stage=%s errorType=%s", stage, type(exc).__name__)

    @staticmethod
    def _raise_provider_unavailable() -> NoReturn:
        raise AppError(
            code=ErrorCode.AI_PROVIDER_ERROR,
            message="AI 답변을 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    @staticmethod
    def _unsupported_response() -> ChatResponse:
        return ChatResponse(
            answer="계약, 지급 일정 또는 자금계획에 대해 질문해 주세요.",
            answer_type="NOT_FOUND",
            citations=[],
            calculation=None,
            used_rag=False,
        )

    @staticmethod
    def _rag_unavailable_response() -> ChatResponse:
        return ChatResponse(
            answer="현재 확인할 수 있는 관련 근거가 없습니다. 계약 조건은 원문과 업체에 확인해 주세요.",
            answer_type="NOT_FOUND",
            citations=[],
            calculation=None,
            used_rag=False,
        )

    @staticmethod
    def _to_response(draft: AnswerDraft) -> ChatResponse:
        return ChatResponse.model_validate(
            {
                "answer": draft.answer,
                "answerType": draft.answer_type,
                "citations": draft.citations,
                "calculation": draft.calculation,
                "usedRag": False,
            }
        )
