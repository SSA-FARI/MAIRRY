from pathlib import Path
from typing import Protocol

from ai.chat_agent.schemas import IntentDecision
from ai.common.types import ToolResultView
from ai.document_extraction.schemas import DocumentExtraction


class DocumentExtractionProvider(Protocol):
    """Provider boundary used by the document extraction application flow."""

    async def extract_document(self, file_path: Path) -> DocumentExtraction: ...


class ChatProvider(Protocol):
    """Provider boundary used by the grounded Chat application flow."""

    async def classify_intent(self, message: str) -> IntentDecision: ...

    async def generate_answer(
        self,
        message: str,
        tool_result: ToolResultView,
    ) -> str: ...


class AiProvider(DocumentExtractionProvider, ChatProvider, Protocol):
    """Full AI adapter boundary implemented by the configured provider."""
