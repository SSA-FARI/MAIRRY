from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import ErrorResponse
from app.domains.contracts.schemas import ContractConfirm, ContractDetailRead, ContractListRead
from app.domains.contracts.service import ContractManagementService, ContractQueryService

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("", response_model=ContractListRead)
def list_contracts(
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ContractListRead:
    return ContractQueryService(db, configuration).list_contracts()


@router.get(
    "/{contract_id}",
    response_model=ContractDetailRead,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found"},
    },
)
def get_contract(
    contract_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ContractDetailRead:
    return ContractQueryService(db, configuration).get_contract(contract_id)


@router.put(
    "/{contract_id}",
    response_model=ContractDetailRead,
    responses={
        404: {"model": ErrorResponse, "description": "Contract not found"},
        422: {"model": ErrorResponse, "description": "Invalid contract data"},
    },
)
def update_contract(
    contract_id: UUID,
    payload: ContractConfirm,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> ContractDetailRead:
    return ContractManagementService(db, configuration).update(contract_id, payload)


@router.delete(
    "/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse, "description": "Contract not found"}},
)
def delete_contract(
    contract_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    configuration: Annotated[Settings, Depends(get_settings)],
) -> Response:
    ContractManagementService(db, configuration).delete(contract_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
