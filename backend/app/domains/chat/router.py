from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.chat_orchestration import ChatOrchestrationService
from app.application.chat_provider import build_chat_provider
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.chat.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, response_model_exclude_defaults=True)
async def chat(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    provider = build_chat_provider(configuration)
    service = ChatOrchestrationService(
        db,
        configuration,
        provider=provider,
    )
    if payload.history:
        return await service.process(payload.message, history=payload.history)
    return await service.process(payload.message)
