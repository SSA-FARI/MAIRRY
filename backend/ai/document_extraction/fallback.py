import json
from pathlib import Path

from ai.document_extraction.schemas import DocumentExtraction


def load_fallback(path: Path) -> DocumentExtraction:
    return DocumentExtraction.model_validate(json.loads(path.read_text(encoding="utf-8")))

