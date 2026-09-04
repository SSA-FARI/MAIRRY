from pathlib import Path
from typing import Protocol

from ai.chat_agent.schemas import IntentDecision
from ai.common.types import ToolResultView
from ai.document_extraction.schemas import DocumentExtraction


class DocumentExtractionProvider(Protocol):
    """Provider boundary used by the document extraction application flow."""

    async def extract_document(self, file_path: Path) -> DocumentExtraction: ...


class AiProvider(DocumentExtractionProvider, Protocol):
    """AI adapter boundary; implementations should normalize SDK failures."""

    async def classify_intent(self, message: str) -> IntentDecision: ...

    async def generate_answer(
        self,
        message: str,
        tool_result: ToolResultView,
    ) -> str: ...
