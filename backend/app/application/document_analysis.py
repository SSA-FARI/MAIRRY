from pathlib import Path

from ai.document_extraction.extractor import analyze_document
from ai.document_extraction.schemas import DocumentAnalysisResult
from ai.providers.base import DocumentExtractionProvider
from ai.providers.openai_provider import OpenAiProvider
from app.core.config import settings


async def run_document_analysis(
    file_path: Path,
    provider: DocumentExtractionProvider | None = None,
) -> DocumentAnalysisResult:
    configured_provider = (
        provider if provider is not None else _build_document_extraction_provider()
    )
    return await analyze_document(
        file_path,
        configured_provider,
        enable_demo_fallback=settings.enable_demo_fallback,
    )


def _build_document_extraction_provider() -> DocumentExtractionProvider | None:
    if not settings.ai_api_key.strip() or not settings.ai_model.strip():
        return None
    return OpenAiProvider(
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
        base_url=settings.ai_base_url,
    )
