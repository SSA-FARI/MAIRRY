from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ErrorResponse
from app.domains.auth.schemas import DemoLoginResponse
from app.domains.auth.service import DemoLoginService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/demo-login",
    response_model=DemoLoginResponse,
    responses={500: {"model": ErrorResponse, "description": "Configuration or server error"}},
    openapi_extra={"security": []},
)
def demo_login(
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> DemoLoginResponse:
    return DemoLoginService(db, configuration).login()
