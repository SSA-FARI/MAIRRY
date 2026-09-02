from collections.abc import Callable

from sqlalchemy.orm import Session

from ai.chat_agent.agent import decide_tool
from ai.chat_agent.fallback import IntentDecision, classify_message
from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.response import AnswerDraft, explain_tool_result
from app.core.config import Settings
from app.domains.chat.schemas import ChatResponse
from app.domains.chat.tools import ChatToolRegistry

IntentClassifier = Callable[[str], IntentDecision]


class ChatOrchestrationService:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        classifier: IntentClassifier = classify_message,
        tool_registry: ChatToolRegistry | None = None,
    ) -> None:
        self._configuration = configuration
        self._classifier = classifier
        self._tools = tool_registry or ChatToolRegistry(session, configuration)

    def process(self, message: str) -> ChatResponse:
        decision = self._classifier(message)
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
        return self._to_response(explain_tool_result(message, result))

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
