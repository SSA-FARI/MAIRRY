from pathlib import Path

from ai.document_extraction.extractor import analyze_document
from ai.document_extraction.schemas import DocumentAnalysisResult
from ai.providers.base import AiProvider
from ai.providers.openai_provider import OpenAiProvider
from app.core.config import settings


def _build_ai_provider() -> AiProvider | None:
    """No provider configured yet (#37) falls back to demo fallback lookup."""
    if not settings.ai_api_key:
        return None
    return OpenAiProvider(api_key=settings.ai_api_key, model=settings.ai_model)


async def run_document_analysis(
    file_path: Path,
    provider: AiProvider | None = None,
) -> DocumentAnalysisResult:
    return await analyze_document(
        file_path,
        provider if provider is not None else _build_ai_provider(),
        enable_demo_fallback=settings.enable_demo_fallback,
    )
