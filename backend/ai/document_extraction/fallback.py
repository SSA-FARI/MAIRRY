import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ai.common.exceptions import DemoFallbackError
from ai.document_extraction.schemas import DocumentExtraction

SHA256_HEX_LENGTH = 64
HASH_READ_CHUNK_SIZE = 1024 * 1024
FALLBACK_ASSET_DIRECTORY = Path(__file__).with_name("fallback_assets")
DEFAULT_DEMO_DOCUMENT_PATH = FALLBACK_ASSET_DIRECTORY / "demo-wedding-hall-contract.pdf"
DEFAULT_DEMO_DOCUMENT_SHA256 = "cf27c6365f9a7410dcff87efafe59b05cd27c0083952fa4e14286b3aadf2217e"
DEFAULT_DEMO_EXTRACTION_PATH = FALLBACK_ASSET_DIRECTORY / "demo-wedding-hall-extraction.json"


@dataclass(frozen=True, slots=True)
class DemoFallbackEntry:
    document_sha256: str
    extraction_path: Path

    def __post_init__(self) -> None:
        normalized_hash = self.document_sha256.lower()
        if len(normalized_hash) != SHA256_HEX_LENGTH:
            raise ValueError("document_sha256 must be a SHA-256 hexadecimal digest")
        try:
            bytes.fromhex(normalized_hash)
        except ValueError as exc:
            raise ValueError("document_sha256 must be a SHA-256 hexadecimal digest") from exc
        object.__setattr__(self, "document_sha256", normalized_hash)


class DemoFallbackRegistry:
    def __init__(self, entries: tuple[DemoFallbackEntry, ...]) -> None:
        self._entries = {entry.document_sha256: entry for entry in entries}
        if len(self._entries) != len(entries):
            raise ValueError("duplicate demo document hash")

    def find(self, document_path: Path) -> DocumentExtraction | None:
        document_hash = calculate_file_sha256(document_path)
        entry = self._entries.get(document_hash)
        if entry is None:
            return None
        return load_fallback(entry.extraction_path)


def calculate_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as document:
            while chunk := document.read(HASH_READ_CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        raise DemoFallbackError("demo fallback could not read the document") from exc
    return digest.hexdigest()


def load_fallback(path: Path) -> DocumentExtraction:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DocumentExtraction.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DemoFallbackError("registered demo fallback is invalid") from exc


DEFAULT_DEMO_FALLBACK_REGISTRY = DemoFallbackRegistry(
    (
        DemoFallbackEntry(
            document_sha256=DEFAULT_DEMO_DOCUMENT_SHA256,
            extraction_path=DEFAULT_DEMO_EXTRACTION_PATH,
        ),
    )
)
