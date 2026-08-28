from pathlib import Path
from typing import Protocol

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_UPLOAD_DIR = _REPOSITORY_ROOT / "uploads" / "documents"


class DocumentStoragePort(Protocol):
    def save(self, storage_key: str, content: bytes, content_type: str) -> str:
        """Persist file bytes and return the reference stored as documents.file_url."""
        ...


class InterimLocalDocumentStorage:
    """Local-disk placeholder for the private-bucket adapter that
    app/integrations/storage/ (MinIO Storage Adapter 이슈) will provide."""

    def __init__(self, base_dir: Path = _DEFAULT_UPLOAD_DIR) -> None:
        self._base_dir = base_dir

    def save(self, storage_key: str, content: bytes, content_type: str) -> str:
        del content_type  # kept for parity with the future S3-compatible adapter's signature
        target = self._base_dir / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target.relative_to(_REPOSITORY_ROOT).as_posix()
