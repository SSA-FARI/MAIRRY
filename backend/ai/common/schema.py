from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class AiContractModel(BaseModel):
    """AI boundary model that accepts Python names and emits contract JSON aliases."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )
