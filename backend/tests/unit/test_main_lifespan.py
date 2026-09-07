import asyncio

from ai.rag import ingest_seed
from app.main import app, lifespan, settings


def test_lifespan_runs_configured_rag_seed_ingestion(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_seed_ingest_on_startup", True)
    monkeypatch.setattr(
        ingest_seed,
        "ingest_configured_seed",
        lambda configuration: calls.append(configuration),
    )

    async def run_lifespan() -> None:
        async with lifespan(app):
            pass

    asyncio.run(run_lifespan())

    assert calls == [settings]
