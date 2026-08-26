from pathlib import Path
from typing import Any, Protocol


class AiProvider(Protocol):
    async def extract_document(self, file_path: Path) -> dict[str, Any]: ...

    async def classify_intent(self, message: str) -> dict[str, Any]: ...

    async def generate_answer(
        self,
        message: str,
        tool_result: dict[str, Any],
    ) -> str: ...
