from datetime import date

import pytest
from pydantic import ValidationError

from app.domains.wedding_plan.schemas import MAX_BIGINT, WeddingPlanUpsert
from app.main import app


@pytest.mark.parametrize("amount", [0, 1, 30_000_000, MAX_BIGINT])
def test_wedding_plan_upsert_accepts_integer_asset_boundaries(amount: int) -> None:
    payload = WeddingPlanUpsert(weddingDate="2027-05-15", availableAsset=amount)

    assert payload.wedding_date == date(2027, 5, 15)
    assert payload.available_asset == amount


@pytest.mark.parametrize(
    "amount",
    [-1, MAX_BIGINT + 1, True, 1.0, 1.5, "30000000", None],
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


def test_wedding_plan_upsert_requires_available_asset() -> None:
    with pytest.raises(ValidationError, match="availableAsset"):
        WeddingPlanUpsert.model_validate({"weddingDate": "2027-05-15"})


@pytest.mark.parametrize("schema_name", ["WeddingPlanUpsert", "WeddingPlanRead"])
def test_generated_openapi_preserves_exact_int64_asset_bounds(schema_name: str) -> None:
    generated_openapi = app.openapi()
    available_asset_schema = generated_openapi["components"]["schemas"][schema_name]["properties"][
        "availableAsset"
    ]

    assert available_asset_schema["type"] == "integer"
    assert available_asset_schema["format"] == "int64"
    assert available_asset_schema["minimum"] == 0
    assert available_asset_schema["maximum"] == MAX_BIGINT
    assert type(available_asset_schema["maximum"]) is int
