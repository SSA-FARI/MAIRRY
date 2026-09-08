import asyncio

import pytest

from ai.rag import ingest_seed
from app import main as main_module
from app.domains.rag.reconciliation import run_reconciliation_loop
from app.main import app, lifespan, settings


def test_lifespan_runs_configured_rag_seed_ingestion(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_seed_ingest_on_startup", True)
    monkeypatch.setattr(settings, "rag_index_reconciliation_enabled", False)
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


def test_reconciliation_runs_immediately_and_periodically_without_real_sleep() -> None:
    calls: list[object] = []
    waits = 0

    def reconcile(configuration) -> int:
        calls.append(configuration)
        return 1

    async def wait(_seconds: float) -> None:
        nonlocal waits
        waits += 1
        if waits == 2:
            raise asyncio.CancelledError

    async def run_loop() -> None:
        with pytest.raises(asyncio.CancelledError):
            await run_reconciliation_loop(
                settings,
                reconcile=reconcile,
                wait=wait,
            )

    asyncio.run(run_loop())

    assert calls == [settings, settings]


def test_lifespan_cancels_reconciliation_and_closes_embedding_clients(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_seed_ingest_on_startup", False)
    monkeypatch.setattr(settings, "rag_index_reconciliation_enabled", True)

    async def reconciliation(_configuration) -> None:
        events.append("started")
        try:
            await asyncio.Event().wait()
        finally:
            events.append("cancelled")

    monkeypatch.setattr(main_module, "run_reconciliation_loop", reconciliation)
    monkeypatch.setattr(
        main_module,
        "close_embedding_http_clients",
        lambda: events.append("clients_closed"),
    )

    async def run_lifespan() -> None:
        async with lifespan(app):
            await asyncio.sleep(0)

    asyncio.run(run_lifespan())

    assert events == ["started", "cancelled", "clients_closed"]
