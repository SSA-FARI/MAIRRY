from datetime import date

import pytest
from pydantic import ValidationError

from app.domains.wedding_plan.schemas import WeddingPlanUpsert


def test_wedding_plan_upsert_accepts_plan_01_values() -> None:
    payload = WeddingPlanUpsert(weddingDate="2027-05-15", availableAsset=30_000_000)

    assert payload.wedding_date == date(2027, 5, 15)
    assert payload.available_asset == 30_000_000


@pytest.mark.parametrize(
    "amount",
    [-1, 9_223_372_036_854_775_808, True, 1.5, "30000000"],
)
def test_wedding_plan_upsert_rejects_invalid_asset(amount: object) -> None:
    with pytest.raises(ValidationError):
        WeddingPlanUpsert(weddingDate="2027-05-15", availableAsset=amount)


def test_wedding_plan_upsert_rejects_unknown_user_id() -> None:
    with pytest.raises(ValidationError, match="userId"):
        WeddingPlanUpsert(
            weddingDate="2027-05-15",
            availableAsset=30_000_000,
            userId="00000000-0000-0000-0000-000000000001",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"availableAsset": 30_000_000},
        {"weddingDate": "not-a-date", "availableAsset": 30_000_000},
    ],
)
def test_wedding_plan_upsert_requires_valid_wedding_date(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WeddingPlanUpsert.model_validate(payload)
