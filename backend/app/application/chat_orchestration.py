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
from ai.chat_agent.fallback import IntentDecision, classify_message, looks_like_expense_simulation
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
    previous_calculation: dict[str, Any] | None


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
        self.calculation_context: dict[str, Any] | None = None
        self.rewritten_question: str | None = None

    async def process(
        self,
        message: str,
        *,
        history: list[str] | None = None,
        referenced_contract_id: UUID | None = None,
        referenced_document_id: UUID | None = None,
        referenced_vendor_name: str | None = None,
        previous_calculation: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.contract_resolution_source = None
        state = await self._graph.ainvoke(
            {
                "question": message,
                "history": (history or [])[-getattr(self._configuration, "rag_history_limit", 8) :],
                "referenced_contract_id": referenced_contract_id,
                "referenced_document_id": referenced_document_id,
                "referenced_vendor_name": referenced_vendor_name,
                "previous_calculation": previous_calculation,
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
        self.rewritten_question = state.get("rewritten_question")
        response = state["response"]
        self.calculation_context = (
            response.calculation.model_dump(mode="json", by_alias=True)
            if response.calculation is not None
            else None
        )
        if (
            self.calculation_context is not None
            and tool_result is not None
            and tool_result.tool_name == "simulateAdditionalExpense"
            and tool_result.data is not None
        ):
            self.calculation_context.update(
                {
                    "expenseName": tool_result.data.get("name"),
                    "additionalExpense": tool_result.data.get("additionalExpense"),
                }
            )
        return response

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
            state.get("previous_calculation"),
        )
        return {"rewritten_question": rewritten, "queries": expand_queries(rewritten)}

    async def _classify(self, state: ChatState) -> dict[str, Any]:
        deterministic = self._classifier(state["question"])
        if deterministic.intent in {
            ChatIntent.GENERAL_CHAT,
            ChatIntent.FOLLOW_UP,
            ChatIntent.NEEDS_CLARIFICATION,
        }:
            return {
                "route": RagRoute.GENERAL,
                "knowledge_types": set(),
                "decision": deterministic,
                "use_provider": False,
            }
        route, knowledge_types = classify_rag_route(state["rewritten_question"])
        decision = IntentDecision(ChatIntent.UNKNOWN, {})
        use_provider = False
        if route in {RagRoute.TOOL, RagRoute.MIXED}:
            if looks_like_expense_simulation(state["rewritten_question"]):
                decision = self._classifier(state["rewritten_question"])
            else:
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
                self._search_rag_with_savepoint,
                state["queries"],
                search_arguments,
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

    def _search_rag_with_savepoint(
        self,
        queries: list[str],
        search_arguments: dict[str, Any],
    ) -> list[RetrievedChunk]:
        begin_nested = getattr(self._session, "begin_nested", None)
        if begin_nested is None:
            return self._rag.search(queries, **search_arguments)
        with begin_nested():
            return self._rag.search(queries, **search_arguments)

    async def _generate(self, state: ChatState) -> dict[str, Any]:
        chunks = state.get("retrieved_chunks", [])
        tool_result = state.get("tool_result")
        if state["route"] == RagRoute.GENERAL:
            intent = state["decision"].intent
            if intent == ChatIntent.GENERAL_CHAT:
                return {"response": general_chat_response(state["question"])}
            if intent == ChatIntent.NEEDS_CLARIFICATION:
                return {"response": self._balance_clarification_response()}
            if intent == ChatIntent.FOLLOW_UP:
                return {"response": self._follow_up_response(state.get("previous_calculation"))}
            if looks_like_expense_simulation(state["question"]):
                return {"response": self._invalid_simulation_response()}
            return {"response": self._unsupported_response()}
        tool_draft = explain_tool_result(state["question"], tool_result) if tool_result else None
        if not chunks:
            if state["route"] == RagRoute.RAG:
                return {
                    "response": self._rag_unavailable_response(
                        retrieval_failed=state.get("retrieval_failed", False),
                        knowledge_types=state.get("knowledge_types", set()),
                    )
                }
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
            in {
                ChatIntent.CONTRACT,
                ChatIntent.CONTRACT_DEPOSIT,
                ChatIntent.CONTRACT_PAYMENT,
                ChatIntent.SCHEDULE,
            }
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
    def _rag_unavailable_response(
        *, retrieval_failed: bool, knowledge_types: set[KnowledgeType]
    ) -> ChatResponse:
        if retrieval_failed:
            answer = "계약 조항을 조회하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        elif KnowledgeType.CONTRACT_CLAUSE in knowledge_types:
            answer = (
                "현재 계약서에서 요청한 취소·환불·해지 조항을 확인하지 못했어요. "
                "계약 상세의 원문을 확인하거나 업체에 문의해 주세요."
            )
        elif KnowledgeType.SERVICE_FAQ in knowledge_types:
            answer = "관련 사용 방법을 찾지 못했어요. 계약 업로드, 지급 일정 또는 자금계획을 구체적으로 질문해 주세요."
        else:
            answer = "현재 확인할 수 있는 관련 정보를 찾지 못했어요. 질문을 조금 더 구체적으로 알려주세요."
        return ChatResponse(
            answer=answer,
            answer_type="NOT_FOUND",
            citations=[],
            calculation=None,
            used_rag=False,
        )

    @staticmethod
    def _invalid_simulation_response() -> ChatResponse:
        return ChatResponse(
            answer="추가 지출 항목과 하나의 정확한 원 단위 금액을 입력해 주세요.",
            answer_type="NOT_FOUND",
            citations=[],
            calculation=None,
            used_rag=False,
        )

    @staticmethod
    def _balance_clarification_response() -> ChatResponse:
        return ChatResponse(
            answer=(
                "계약별로 아직 지급하지 않은 잔금을 말씀하시는 건가요, "
                "아니면 모든 예정 지출을 제외한 예상 잔액을 말씀하시는 건가요?"
            ),
            answer_type="GENERAL",
            citations=[],
            calculation=None,
            used_rag=False,
        )

    @staticmethod
    def _follow_up_response(previous: dict[str, Any] | None) -> ChatResponse:
        required_fields = {
            "toolName",
            "currentExpectedBalance",
            "simulatedExpectedBalance",
            "shortageAmount",
            "calculatedAt",
        }
        if (
            not previous
            or previous.get("toolName") != "simulateAdditionalExpense"
            or not required_fields.issubset(previous)
        ):
            return ChatResponse(
                answer=(
                    "어떤 지출이나 금액을 말씀하시는지 한 번 더 알려주세요. "
                    "예: 가전제품 구매에 300만 원을 써도 될까?"
                ),
                answer_type="GENERAL",
                citations=[],
                calculation=None,
                used_rag=False,
            )
        shortage = int(previous["shortageAmount"])
        balance = int(previous["simulatedExpectedBalance"])
        if shortage > 0:
            answer = (
                f"직전 추가 지출을 반영하면 예상 잔액이 {balance:,}원이고 "
                f"{shortage:,}원이 부족해, 현재 계획 기준으로는 예산이 부족합니다."
            )
        else:
            answer = (
                f"현재 확정된 계약과 지급 일정을 기준으로는 직전 추가 지출을 반영해도 "
                f"예상 잔액이 {balance:,}원 남아 예산 부족 상태는 아니에요. "
                "다만 아직 확정되지 않은 계약이나 추가 비용은 반영되지 않았으니 함께 고려해 주세요."
            )
        return ChatResponse.model_validate(
            {
                "answer": answer,
                "answerType": "CALCULATION",
                "citations": [],
                "calculation": {
                    key: previous[key]
                    for key in (
                        "toolName",
                        "currentExpectedBalance",
                        "simulatedExpectedBalance",
                        "shortageAmount",
                        "calculatedAt",
                    )
                },
                "usedRag": False,
            }
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


def general_chat_response(message: str) -> ChatResponse:
    normalized = " ".join(message.strip().split())
    if any(word in normalized for word in ("고마워", "고맙습니다", "감사해", "감사합니다")):
        answer = "도움이 되었다니 다행이에요. 다른 계약이나 예산도 궁금하면 물어보세요."
    elif any(
        phrase in normalized
        for phrase in ("어떤 걸 물어볼 수 있어", "무엇을 물어볼 수 있어", "뭘 물어볼 수 있어")
    ):
        answer = (
            "확정 계약의 금액과 취소 조건, 가까운 지급 일정, 남은 지출과 예상 잔액, "
            "추가 지출 시뮬레이션을 물어볼 수 있어요."
        )
    else:
        answer = "안녕하세요! 계약 내용, 지급 일정, 남은 예산에 관해 무엇이든 물어보세요."
    return ChatResponse(
        answer=answer,
        answer_type="GENERAL",
        citations=[],
        calculation=None,
        used_rag=False,
    )
