from types import SimpleNamespace
from uuid import UUID

import pytest

from app.core.errors import AppError
from app.domains.chat.models import ChatConversation, ChatMessage
from app.domains.chat.schemas import ChatResponse
from app.domains.chat.service import ChatConversationService

USER_ID = UUID(int=1)
OTHER_USER_ID = UUID(int=2)
PLAN_ID = UUID(int=3)
CONVERSATION_ID = UUID(int=4)
CONTRACT_ID = UUID(int=5)
DOCUMENT_ID = UUID(int=6)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeChatRepository:
    def __init__(
        self,
        conversation: ChatConversation | None = None,
        messages: list[ChatMessage] | None = None,
    ) -> None:
        self.conversation = conversation
        self.messages = messages or []
        self.added_messages: list[ChatMessage] = []

    def get_accessible_conversation(self, conversation_id: UUID, user_id: UUID):
        if (
            self.conversation is not None
            and self.conversation.id == conversation_id
            and self.conversation.created_by_user_id == user_id
        ):
            return self.conversation
        return None

    def recent_messages(self, _conversation_id: UUID, limit: int):
        return self.messages[-limit:]

    def add_conversation(self, conversation: ChatConversation) -> None:
        conversation.id = CONVERSATION_ID
        self.conversation = conversation

    def add_message(self, message: ChatMessage) -> None:
        message.id = UUID(int=20 + len(self.added_messages))
        self.added_messages.append(message)


def _service(repository: FakeChatRepository, *, plan_id: UUID = PLAN_ID):
    service = ChatConversationService.__new__(ChatConversationService)
    service._session = FakeSession()
    service._repository = repository
    service._plans = SimpleNamespace(
        get_current_for_user=lambda _user_id: SimpleNamespace(id=plan_id)
    )
    return service


def test_conversation_restores_recent_roles_and_referenced_contract_context() -> None:
    conversation = ChatConversation(
        id=CONVERSATION_ID,
        wedding_plan_id=PLAN_ID,
        created_by_user_id=USER_ID,
    )
    repository = FakeChatRepository(
        conversation,
        [
            ChatMessage(
                conversation_id=CONVERSATION_ID,
                role="user",
                content="라온벨 해지 수수료 알려줘",
            ),
            ChatMessage(
                conversation_id=CONVERSATION_ID,
                role="assistant",
                content="계약서 근거를 확인했습니다.",
                context_data={
                    "referencedContractId": str(CONTRACT_ID),
                    "referencedDocumentId": str(DOCUMENT_ID),
                    "referencedVendorName": "라온벨 웨딩컨벤션",
                },
            ),
        ],
    )
    service = _service(repository)

    turn = service.begin_turn(
        conversation_id=CONVERSATION_ID,
        user_id=USER_ID,
        message="위 계약 예약금 얼마야?",
        history_limit=8,
    )

    assert turn.history == [
        "사용자: 라온벨 해지 수수료 알려줘",
        "AI: 계약서 근거를 확인했습니다.",
    ]
    assert turn.referenced_contract_id == CONTRACT_ID
    assert turn.referenced_document_id == DOCUMENT_ID
    assert turn.referenced_vendor_name == "라온벨 웨딩컨벤션"
    assert repository.added_messages[-1].role == "user"


def test_conversation_rejects_other_user_or_other_current_plan() -> None:
    conversation = ChatConversation(
        id=CONVERSATION_ID,
        wedding_plan_id=PLAN_ID,
        created_by_user_id=USER_ID,
    )
    repository = FakeChatRepository(conversation)

    with pytest.raises(AppError):
        _service(repository).begin_turn(
            conversation_id=CONVERSATION_ID,
            user_id=OTHER_USER_ID,
            message="이전 대화 보여줘",
            history_limit=8,
        )

    with pytest.raises(AppError):
        _service(repository, plan_id=UUID(int=99)).begin_turn(
            conversation_id=CONVERSATION_ID,
            user_id=USER_ID,
            message="이전 대화 보여줘",
            history_limit=8,
        )


def test_assistant_message_persists_reference_context_and_commits() -> None:
    repository = FakeChatRepository()
    service = _service(repository)
    turn = service.begin_turn(
        conversation_id=None,
        user_id=USER_ID,
        message="라온벨 예약금 얼마야?",
        history_limit=8,
    )
    response = ChatResponse(
        answer="예약금은 3,000,000원이며 지급 완료 상태입니다.",
        answer_type="CONTRACT",
        citations=[],
        calculation=None,
    )

    message_id = service.complete_turn(
        turn,
        response,
        referenced_contract_id=CONTRACT_ID,
        referenced_document_id=DOCUMENT_ID,
        referenced_vendor_name="라온벨 웨딩컨벤션",
    )

    assistant = repository.added_messages[-1]
    assert message_id == assistant.id
    assert assistant.context_data == {
        "referencedContractId": str(CONTRACT_ID),
        "referencedDocumentId": str(DOCUMENT_ID),
        "referencedVendorName": "라온벨 웨딩컨벤션",
    }
    assert service._session.committed is True
