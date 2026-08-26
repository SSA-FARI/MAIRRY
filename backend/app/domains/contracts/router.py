from fastapi import APIRouter

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("")
def list_contracts() -> dict[str, list[object]]:
    return {"items": []}


@router.get("/{contract_id}")
def get_contract(contract_id: str) -> dict[str, str]:
    return {"id": contract_id, "status": "not_implemented"}
