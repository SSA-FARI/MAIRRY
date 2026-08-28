from pathlib import Path

from ai.document_extraction.extractor import analyze_document
from ai.document_extraction.schemas import DocumentAnalysisResult
from ai.providers.base import AiProvider
from app.core.config import settings


async def run_document_analysis(
    file_path: Path,
    provider: AiProvider | None = None,
) -> DocumentAnalysisResult:
    return await analyze_document(
        file_path,
        provider,
        enable_demo_fallback=settings.enable_demo_fallback,
    )
