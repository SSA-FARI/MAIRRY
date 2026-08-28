from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.domains.auth.router import router as auth_router
from app.domains.chat.router import router as chat_router
from app.domains.contracts.router import router as contracts_router
from app.domains.documents.router import router as documents_router
from app.domains.finance.router import router as finance_router
from app.domains.wedding_plan.router import router as wedding_plan_router
from app.domains.wedding_plan.schemas import WeddingPlanRead, WeddingPlanUpsert


class MairryAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        openapi_schema = super().openapi()
        component_schemas = openapi_schema.get("components", {}).get("schemas", {})

        # FastAPI models JSON Schema numeric bounds as float. Restore these integer
        # fields from Pydantic's exact schema after FastAPI assembles the document.
        for model in (WeddingPlanUpsert, WeddingPlanRead):
            source_property = model.model_json_schema(by_alias=True)["properties"]["availableAsset"]
            target_property = (
                component_schemas.get(model.__name__, {})
                .get("properties", {})
                .get("availableAsset")
            )
            if target_property is None:
                continue
            target_property["minimum"] = source_property["minimum"]
            target_property["maximum"] = source_property["maximum"]

        return openapi_schema


app = MairryAPI(title="MAIRRY API", version="0.1.0")
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(wedding_plan_router, prefix="/api")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api")
app.include_router(contracts_router, prefix="/api")
app.include_router(finance_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
