import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from ai.common.exceptions import AiOutputError, AiProviderError, DemoFallbackError
from ai.document_extraction.extractor import analyze_document
from ai.document_extraction.fallback import DEFAULT_DEMO_DOCUMENT_PATH, DemoFallbackRegistry


class SuccessfulProvider:
    async def extract_document(self, file_path: Path) -> dict[str, Any]:
        return {
            "documentType": "WEDDING_HALL",
            "company": "실시간 분석 웨딩홀",
            "totalPrice": 10_000_000,
            "payments": [],
            "cancellationTerms": [],
            "warnings": [],
        }


class FailingProvider:
    async def extract_document(self, file_path: Path) -> dict[str, Any]:
        raise AiProviderError("provider response that must not leak")


class InvalidOutputProvider:
    async def extract_document(self, file_path: Path) -> dict[str, Any]:
        return {
            "documentType": "WEDDING_HALL",
            "company": "잘못된 결과",
            "totalPrice": -1,
            "payments": [],
            "cancellationTerms": [],
            "warnings": [],
        }


class UnexpectedFailureProvider:
    async def extract_document(self, file_path: Path) -> dict[str, Any]:
        raise ConnectionResetError("network details that must not leak")


class FailingFallbackRegistry(DemoFallbackRegistry):
    def find(self, document_path: Path) -> None:
        raise DemoFallbackError("fallback details that must not leak")


class ThreadRecordingFallbackRegistry(DemoFallbackRegistry):
    def __init__(self) -> None:
        super().__init__(())
        self.worker_thread_id: int | None = None

    def find(self, document_path: Path) -> None:
        self.worker_thread_id = threading.get_ident()


def test_live_provider_result_has_priority_over_demo_fallback() -> None:
    result = asyncio.run(analyze_document(DEFAULT_DEMO_DOCUMENT_PATH, SuccessfulProvider()))

    assert result.analysis_source == "LIVE_AI"
    assert result.extraction.company == "실시간 분석 웨딩홀"


@pytest.mark.parametrize(
    "provider",
    [None, FailingProvider(), InvalidOutputProvider(), UnexpectedFailureProvider()],
)
def test_registered_document_uses_fallback_when_provider_is_unavailable(provider: Any) -> None:
    result = asyncio.run(analyze_document(DEFAULT_DEMO_DOCUMENT_PATH, provider))

    assert result.analysis_source == "DEMO_FALLBACK"
    assert result.model_dump(mode="json")["analysisSource"] == "DEMO_FALLBACK"
    assert result.extraction.company == "A웨딩홀"
    assert result.extraction.payments[1].amount == 20_000_000


def test_disabled_fallback_does_not_return_demo_result() -> None:
    with pytest.raises(AiProviderError, match="AI provider is not configured"):
        asyncio.run(
            analyze_document(
                DEFAULT_DEMO_DOCUMENT_PATH,
                enable_demo_fallback=False,
            )
        )


def test_unregistered_document_does_not_use_fallback(tmp_path: Path) -> None:
    document_path = tmp_path / DEFAULT_DEMO_DOCUMENT_PATH.name
    document_path.write_bytes(b"unregistered document")

    with pytest.raises(AiProviderError, match="AI provider request failed") as error:
        asyncio.run(analyze_document(document_path, FailingProvider()))

    assert str(error.value) == "AI provider request failed"


def test_invalid_provider_output_is_rejected_without_matching_fallback(tmp_path: Path) -> None:
    document_path = tmp_path / "unknown-document.pdf"
    document_path.write_bytes(b"unknown document")

    with pytest.raises(AiOutputError, match="invalid extraction"):
        asyncio.run(analyze_document(document_path, InvalidOutputProvider()))


def test_fallback_lookup_failure_does_not_hide_provider_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(AiProviderError, match="AI provider request failed") as error:
        asyncio.run(
            analyze_document(
                DEFAULT_DEMO_DOCUMENT_PATH,
                FailingProvider(),
                fallback_registry=FailingFallbackRegistry(()),
            )
        )

    assert str(error.value) == "AI provider request failed"
    assert "fallback details" not in caplog.text
    assert "provider response" not in caplog.text
    assert "Demo fallback lookup failed" in caplog.text


def test_fallback_lookup_runs_outside_event_loop_thread() -> None:
    registry = ThreadRecordingFallbackRegistry()
    event_loop_thread_id = threading.get_ident()

    with pytest.raises(AiProviderError, match="AI provider is not configured"):
        asyncio.run(
            analyze_document(
                DEFAULT_DEMO_DOCUMENT_PATH,
                fallback_registry=registry,
            )
        )

    assert registry.worker_thread_id is not None
    assert registry.worker_thread_id != event_loop_thread_id


def test_provider_failure_log_keeps_only_safe_error_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = asyncio.run(
        analyze_document(
            DEFAULT_DEMO_DOCUMENT_PATH,
            UnexpectedFailureProvider(),
        )
    )

    assert result.analysis_source == "DEMO_FALLBACK"
    assert "errorType=ConnectionResetError" in caplog.text
    assert "network details" not in caplog.text
