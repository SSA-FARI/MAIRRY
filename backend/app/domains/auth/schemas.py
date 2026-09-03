from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schema import ApiModel


class DemoUserRead(ApiModel):
    id: UUID
    login_id: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=50)
    email: str | None = Field(max_length=255)


class DemoLoginResponse(ApiModel):
    user: DemoUserRead
    mode: Literal["DEMO"] = "DEMO"
