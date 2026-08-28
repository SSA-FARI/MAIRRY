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

app = FastAPI(title="MAIRRY API", version="0.1.0")
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
