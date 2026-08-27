import asyncio
from pathlib import Path
from typing import Any

import pytest

from ai.common.exceptions import AiOutputError, AiProviderError
from ai.document_extraction.extractor import analyze_document
from ai.document_extraction.fallback import DEFAULT_DEMO_DOCUMENT_PATH


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


def test_live_provider_result_has_priority_over_demo_fallback() -> None:
    result = asyncio.run(analyze_document(DEFAULT_DEMO_DOCUMENT_PATH, SuccessfulProvider()))

    assert result.analysis_source == "LIVE_AI"
    assert result.extraction.company == "실시간 분석 웨딩홀"


@pytest.mark.parametrize("provider", [None, FailingProvider(), InvalidOutputProvider()])
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
