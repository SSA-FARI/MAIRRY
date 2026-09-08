import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.domains.auth.router import router as auth_router
from app.domains.chat.router import router as chat_router
from app.domains.contracts.router import router as contracts_router
from app.domains.documents.router import router as documents_router
from app.domains.finance.router import router as finance_router
from app.domains.rag.reconciliation import run_reconciliation_loop
from app.domains.rag.service import close_embedding_http_clients
from app.domains.wedding_plan.router import router as wedding_plan_router
from app.domains.wedding_plan.schemas import WeddingPlanRead, WeddingPlanUpsert

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.rag_enabled and settings.rag_seed_ingest_on_startup:
        try:
            from ai.rag.ingest_seed import ingest_configured_seed

            await run_in_threadpool(ingest_configured_seed, settings)
        except Exception as exc:
            logger.exception(
                "RAG seed startup ingestion failed: errorType=%s",
                type(exc).__name__,
            )
    reconciliation_task: asyncio.Task[None] | None = None
    if settings.rag_enabled and settings.rag_index_reconciliation_enabled:
        reconciliation_task = asyncio.create_task(
            run_reconciliation_loop(settings),
            name="rag-index-reconciliation",
        )
    try:
        yield
    finally:
        if reconciliation_task is not None:
            reconciliation_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconciliation_task
        close_embedding_http_clients()


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


app = MairryAPI(title="MAIRRY API", version="0.1.0", lifespan=lifespan)
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
