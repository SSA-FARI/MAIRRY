from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ErrorResponse
from app.domains.wedding_plan.schemas import WeddingPlanRead, WeddingPlanUpsert
from app.domains.wedding_plan.service import WeddingPlanService

router = APIRouter(prefix="/wedding-plan", tags=["wedding-plan"])


@router.get(
    "",
    response_model=WeddingPlanRead,
    responses={
        404: {"model": ErrorResponse, "description": "Wedding plan not found"},
    },
)
def get_wedding_plan(
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> WeddingPlanRead:
    return WeddingPlanService(db, configuration).get_current()


@router.put(
    "",
    response_model=WeddingPlanRead,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
def upsert_wedding_plan(
    payload: WeddingPlanUpsert,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> WeddingPlanRead:
    return WeddingPlanService(db, configuration).upsert(payload)
