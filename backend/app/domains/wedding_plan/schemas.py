from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.core.schema import ApiModel

MAX_BIGINT = 9_223_372_036_854_775_807


class WeddingPlanUpsert(ApiModel):
    wedding_date: date
    available_asset: Annotated[
        int,
        Field(
            strict=True,
            ge=0,
            le=MAX_BIGINT,
            description="Representative joint cash asset entered during WeddingPlan setup.",
            json_schema_extra={"format": "int64"},
        ),
    ]


class WeddingPlanRead(WeddingPlanUpsert):
    id: UUID
