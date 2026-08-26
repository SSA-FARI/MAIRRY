from pathlib import Path

from ai.document_extraction.schemas import DocumentExtraction
from ai.providers.base import AiProvider


async def analyze_document(
    file_path: Path,
    provider: AiProvider | None = None,
) -> DocumentExtraction:
    if provider is None:
        raise NotImplementedError("AI provider must be configured")
    payload = await provider.extract_document(file_path)
    return DocumentExtraction.model_validate(payload)
