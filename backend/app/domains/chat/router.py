import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai.chat_agent.fallback import classify_message
from ai.chat_agent.intent import ChatIntent
from app.application.chat_orchestration import ChatOrchestrationService, general_chat_response
from app.application.chat_provider import build_chat_provider
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.chat.schemas import ChatRequest, ChatResponse
from app.domains.chat.service import ChatConversationService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse, response_model_exclude_defaults=True)
async def chat(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    if (
        payload.conversation_id is None
        and classify_message(payload.message).intent == ChatIntent.GENERAL_CHAT
    ):
        return general_chat_response(payload.message)
    conversations = ChatConversationService(db)
    try:
        turn = conversations.begin_turn(
            conversation_id=payload.conversation_id,
            user_id=configuration.demo_user_id,
            message=payload.message,
            history_limit=getattr(configuration, "rag_history_limit", 8),
        )
        if turn is None:
            return ChatResponse(
                answer=(
                    "아직 웨딩 계획이 없어 자금 정보를 확인할 수 없습니다. "
                    "먼저 결혼 예정일과 초기 자산을 설정해 주세요."
                ),
                answer_type="NOT_FOUND",
                citations=[],
                calculation=None,
            )
        service = ChatOrchestrationService(
            db,
            configuration,
            provider=build_chat_provider(configuration),
        )
        response = await service.process(
            payload.message,
            history=turn.history,
            referenced_contract_id=turn.referenced_contract_id,
            referenced_document_id=turn.referenced_document_id,
            referenced_vendor_name=turn.referenced_vendor_name,
            previous_calculation=turn.previous_calculation,
        )
        message_id = conversations.complete_turn(
            turn,
            response,
            referenced_contract_id=service.referenced_contract_id,
            referenced_document_id=service.referenced_document_id,
            referenced_vendor_name=service.referenced_vendor_name,
            calculation_context=service.calculation_context,
        )
        logger.info(
            "Chat turn completed: conversationId=%s historyMessageCount=%s "
            "intent=%s tool=%s contractResolutionSource=%s resolvedContractId=%s "
            "ragUsed=%s retrievedChunkCount=%s citationCount=%s",
            turn.conversation.id,
            len(turn.history),
            service.intent,
            service.tool_name,
            service.contract_resolution_source,
            service.referenced_contract_id,
            response.used_rag,
            service.retrieved_chunk_count,
            len(response.citations),
        )
        return response.model_copy(
            update={"conversation_id": turn.conversation.id, "message_id": message_id}
        )
    except Exception:
        conversations.rollback()
        raise
