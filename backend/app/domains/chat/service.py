from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.chat.models import ChatConversation, ChatMessage
from app.domains.chat.repository import ChatRepository
from app.domains.chat.schemas import ChatResponse
from app.domains.wedding_plan.repository import WeddingPlanRepository


@dataclass(frozen=True)
class ConversationTurn:
    conversation: ChatConversation
    history: list[str]
    referenced_contract_id: UUID | None
    referenced_document_id: UUID | None
    referenced_vendor_name: str | None


class ChatConversationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ChatRepository(session)
        self._plans = WeddingPlanRepository(session)

    def begin_turn(
        self, *, conversation_id: UUID | None, user_id: UUID, message: str, history_limit: int
    ) -> ConversationTurn:
        plan = self._plans.get_current_for_user(user_id)
        if plan is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "현재 웨딩 계획을 찾을 수 없습니다.", 404)
        if conversation_id is None:
            conversation = ChatConversation(
                wedding_plan_id=plan.id,
                created_by_user_id=user_id,
            )
            self._repository.add_conversation(conversation)
        else:
            conversation = self._repository.get_accessible_conversation(conversation_id, user_id)
            if conversation is None or conversation.wedding_plan_id != plan.id:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "대화를 찾을 수 없습니다.", 404)

        previous = self._repository.recent_messages(conversation.id, history_limit * 2)
        context = next(
            (
                item.context_data
                for item in reversed(previous)
                if item.role == "assistant" and item.context_data
            ),
            {},
        )
        self._repository.add_message(
            ChatMessage(conversation_id=conversation.id, role="user", content=message)
        )
        return ConversationTurn(
            conversation=conversation,
            history=[
                f"{'사용자' if item.role == 'user' else 'AI'}: {item.content}" for item in previous
            ],
            referenced_contract_id=_optional_uuid(context.get("referencedContractId")),
            referenced_document_id=_optional_uuid(context.get("referencedDocumentId")),
            referenced_vendor_name=_optional_string(context.get("referencedVendorName")),
        )

    def complete_turn(
        self,
        turn: ConversationTurn,
        response: ChatResponse,
        *,
        referenced_contract_id: UUID | None,
        referenced_document_id: UUID | None,
        referenced_vendor_name: str | None,
    ) -> UUID:
        message = ChatMessage(
            conversation_id=turn.conversation.id,
            role="assistant",
            content=response.answer,
            context_data={
                key: value
                for key, value in {
                    "referencedContractId": str(referenced_contract_id)
                    if referenced_contract_id
                    else None,
                    "referencedDocumentId": str(referenced_document_id)
                    if referenced_document_id
                    else None,
                    "referencedVendorName": referenced_vendor_name,
                }.items()
                if value is not None
            },
        )
        self._repository.add_message(message)
        self._session.commit()
        return message.id

    def rollback(self) -> None:
        self._session.rollback()


def _optional_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
