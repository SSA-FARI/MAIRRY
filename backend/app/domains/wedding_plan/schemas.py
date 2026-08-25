from datetime import date

from pydantic import Field

from app.core.schema import ApiModel


class WeddingPlanUpsert(ApiModel):
    wedding_date: date
    available_asset: int = Field(ge=0)


class WeddingPlanRead(WeddingPlanUpsert):
    id: str
