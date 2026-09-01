from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ErrorResponse
from app.domains.finance.schemas import FinanceSummary, SimulationRequest, SimulationResult
from app.domains.finance.service import FinanceService

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get(
    "/summary",
    response_model=FinanceSummary,
    responses={404: {"model": ErrorResponse, "description": "Wedding plan not found"}},
)
def get_finance_summary(
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> FinanceSummary:
    return FinanceService(db, configuration).get_summary()


@router.post(
    "/simulate",
    response_model=SimulationResult,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Wedding plan not found"},
    },
)
def simulate_finance(
    payload: SimulationRequest,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> SimulationResult:
    return FinanceService(db, configuration).simulate(payload.amount)
