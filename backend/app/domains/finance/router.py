from fastapi import APIRouter

from app.domains.finance.schemas import SimulationRequest

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/summary")
def get_finance_summary() -> dict[str, int | None]:
    return {
        "availableAsset": 0,
        "remainingExpense": 0,
        "expectedBalance": 0,
        "nearestPayment": None,
    }


@router.post("/simulate")
def simulate_finance(payload: SimulationRequest) -> dict[str, int]:
    return {
        "currentExpectedBalance": 0,
        "simulatedExpectedBalance": -payload.amount,
        "shortageAmount": payload.amount,
    }
