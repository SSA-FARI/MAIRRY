import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace

from sqlalchemy.orm import Session

from ai.chat_agent.agent import decide_tool
from ai.chat_agent.fallback import IntentDecision, classify_message
from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.response import AnswerDraft, explain_tool_result
from ai.common.exceptions import AiError
from ai.common.types import ToolResultView
from ai.providers.base import AiProvider
from ai.providers.openai_provider import OpenAiProvider
from app.core.config import Settings
from app.domains.chat.schemas import ChatResponse
from app.domains.chat.tools import ChatToolRegistry

IntentClassifier = Callable[[str], IntentDecision]
logger = logging.getLogger(__name__)


def _build_ai_provider(configuration: Settings) -> AiProvider | None:
    api_key = getattr(configuration, "ai_api_key", "")
    model = getattr(configuration, "ai_model", "")
    if not api_key or not model:
        return None
    return OpenAiProvider(
        api_key=api_key,
        model=model,
        timeout_seconds=getattr(configuration, "ai_timeout_seconds", 45),
    )


class ChatOrchestrationService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        classifier: IntentClassifier = classify_message,
        tool_registry: ChatToolRegistry | None = None,
        ai_provider: AiProvider | None = None,
    ) -> None:
        self._configuration = configuration
        self._fallback_classifier = classifier
        self._tools = tool_registry or ChatToolRegistry(session, configuration)
        self._ai_provider = (
            ai_provider if ai_provider is not None else _build_ai_provider(configuration)
        )

    def process(self, message: str) -> ChatResponse:
        decision, use_provider_answer = self._classify_intent(message)
        if decision.intent == ChatIntent.UNKNOWN:
            return self._unsupported_response()

        arguments = dict(decision.arguments)
        if (
            decision.intent in {ChatIntent.CONTRACT, ChatIntent.SCHEDULE}
            and "contractId" not in arguments
        ):
            contract_id = self._tools.resolve_contract_id(
                message,
                self._configuration.demo_user_id,
            )
            if contract_id is not None:
                arguments["contractId"] = str(contract_id)

        call = decide_tool(decision.intent, arguments)
        if call is None:
            return self._unsupported_response()
        result = self._tools.execute(
            call.tool_name,
            call.arguments,
            self._configuration.demo_user_id,
        )
        draft = explain_tool_result(message, result)
        if use_provider_answer and result.status == "SUCCESS" and result.data is not None:
            draft = self._generate_answer(message, result, draft)
        return self._to_response(draft)

    def _classify_intent(self, message: str) -> tuple[IntentDecision, bool]:
        if self._ai_provider is not None:
            try:
                decision = asyncio.run(self._ai_provider.classify_intent(message))
                logger.info(
                    "Chat AI intent classification completed: intent=%s",
                    decision.intent.value,
                )
                return decision, True
            except AiError as exc:
                self._log_fallback("intent classification", exc)
        return self._fallback_classifier(message), False

    def _generate_answer(
        self,
        message: str,
        result: ToolResultView,
        fallback_draft: AnswerDraft,
    ) -> AnswerDraft:
        assert self._ai_provider is not None
        try:
            answer = asyncio.run(self._ai_provider.generate_answer(message, result))
        except AiError as exc:
            self._log_fallback("answer generation", exc)
            return fallback_draft
        logger.info(
            "Chat AI answer generation completed: toolName=%s",
            result.tool_name,
        )
        return replace(fallback_draft, answer=answer)

    @staticmethod
    def _log_fallback(stage: str, exc: AiError) -> None:
        logger.warning(
            "Chat AI %s failed; using deterministic fallback: errorType=%s",
            stage,
            type(exc).__name__,
        )

    @staticmethod
    def _unsupported_response() -> ChatResponse:
        return ChatResponse(
            answer="계약, 지급 일정 또는 자금계획에 대해 질문해 주세요.",
            answer_type="NOT_FOUND",
            citations=[],
            calculation=None,
        )

    @staticmethod
    def _to_response(draft: AnswerDraft) -> ChatResponse:
        return ChatResponse.model_validate(
            {
                "answer": draft.answer,
                "answerType": draft.answer_type,
                "citations": draft.citations,
                "calculation": draft.calculation,
            }
        )
