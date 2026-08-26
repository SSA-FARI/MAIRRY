from pathlib import Path

from ai.document_extraction.extractor import analyze_document
from ai.document_extraction.schemas import DocumentExtraction
from ai.providers.base import AiProvider


async def run_document_analysis(
    file_path: Path,
    provider: AiProvider,
) -> DocumentExtraction:
    return await analyze_document(file_path, provider)
