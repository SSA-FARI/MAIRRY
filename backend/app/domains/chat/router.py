from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.chat_orchestration import ChatOrchestrationService
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.chat.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    return ChatOrchestrationService(db, configuration).process(payload.message)
