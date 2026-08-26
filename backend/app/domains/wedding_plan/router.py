from fastapi import APIRouter

from app.domains.wedding_plan.schemas import WeddingPlanUpsert

router = APIRouter(prefix="/wedding-plan", tags=["wedding-plan"])


@router.get("")
def get_wedding_plan() -> dict[str, str]:
    return {"status": "not_implemented"}


@router.put("")
def upsert_wedding_plan(payload: WeddingPlanUpsert) -> WeddingPlanUpsert:
    return payload
