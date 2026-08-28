from pathlib import Path
from typing import Any, Protocol

from ai.document_extraction.schemas import DocumentExtraction


class DocumentExtractionProvider(Protocol):
    """Provider boundary used by the document extraction application flow."""

    async def extract_document(self, file_path: Path) -> DocumentExtraction: ...


class AiProvider(DocumentExtractionProvider, Protocol):
    """AI adapter boundary; implementations should normalize SDK failures."""

    async def classify_intent(self, message: str) -> dict[str, Any]: ...

    async def generate_answer(
        self,
        message: str,
        tool_result: dict[str, Any],
    ) -> str: ...
