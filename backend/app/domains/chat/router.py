from fastapi import APIRouter

from app.domains.chat.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(payload: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer="대화 오케스트레이터 구현이 필요합니다.",
        answer_type="NOT_FOUND",
        citations=[],
        calculation=None,
    )
