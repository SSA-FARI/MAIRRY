from pathlib import Path
from typing import Any


class OpenAiProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def extract_document(self, file_path: Path) -> dict[str, Any]:
        raise NotImplementedError

    async def classify_intent(self, message: str) -> dict[str, Any]:
        raise NotImplementedError

    async def generate_answer(
        self,
        message: str,
        tool_result: dict[str, Any],
    ) -> str:
        raise NotImplementedError
