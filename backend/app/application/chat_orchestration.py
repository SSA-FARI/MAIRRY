import logging
from collections.abc import Callable
from dataclasses import replace
from typing import NoReturn

from fastapi import status
from sqlalchemy.orm import Session

from ai.chat_agent.agent import decide_tool
from ai.chat_agent.fallback import IntentDecision, classify_message
from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.response import AnswerDraft, explain_tool_result
from ai.common.exceptions import AiError
from ai.common.types import ToolResultView
from ai.providers.base import ChatProvider
from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.chat.schemas import ChatResponse
from app.domains.chat.tools import ChatToolRegistry

IntentClassifier = Callable[[str], IntentDecision]
logger = logging.getLogger(__name__)


class ChatOrchestrationService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        classifier: IntentClassifier = classify_message,
        provider: ChatProvider | None = None,
        tool_registry: ChatToolRegistry | None = None,
    ) -> None:
        self._configuration = configuration
        self._classifier = classifier
        self._provider = provider
        self._tools = tool_registry or ChatToolRegistry(session, configuration)

    async def process(self, message: str) -> ChatResponse:
        decision, use_provider_for_answer = await self._classify_intent(message)
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
        draft = await self._generate_answer(
            message,
            result,
            draft,
            use_provider=use_provider_for_answer,
        )
        return self._to_response(draft)

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

    async def _generate_answer(
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

    @staticmethod
    def _log_provider_failure(stage: str, exc: AiError) -> None:
        logger.warning(
            "Chat AI provider failed: stage=%s errorType=%s",
            stage,
            type(exc).__name__,
        )

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
