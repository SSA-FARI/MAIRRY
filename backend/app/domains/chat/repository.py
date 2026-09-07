from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.chat.models import ChatConversation, ChatMessage


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_accessible_conversation(
        self, conversation_id: UUID, user_id: UUID
    ) -> ChatConversation | None:
        return self._session.scalar(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.created_by_user_id == user_id,
            )
        )

    def recent_messages(self, conversation_id: UUID, limit: int) -> list[ChatMessage]:
        rows = list(
            self._session.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(limit)
            ).all()
        )
        return list(reversed(rows))

    def add_conversation(self, conversation: ChatConversation) -> None:
        self._session.add(conversation)
        self._session.flush()

    def add_message(self, message: ChatMessage) -> None:
        self._session.add(message)
        self._session.flush()
