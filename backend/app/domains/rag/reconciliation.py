import asyncio
import logging
from collections.abc import Awaitable, Callable

from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.domains.rag.service import reconcile_index_jobs

logger = logging.getLogger(__name__)


async def run_reconciliation_loop(
    configuration: Settings,
    *,
    reconcile: Callable[[Settings], int] = reconcile_index_jobs,
    wait: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Recover retryable RAG jobs until the application lifespan is cancelled."""
    while True:
        try:
            processed = await run_in_threadpool(reconcile, configuration)
            if processed:
                logger.info("RAG index reconciliation completed: processed=%s", processed)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the recovery loop must survive one job cycle
            logger.error(
                "RAG index reconciliation failed: errorType=%s",
                type(exc).__name__,
            )
        await wait(configuration.rag_index_reconciliation_interval_seconds)
