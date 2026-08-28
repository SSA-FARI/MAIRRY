from typing import Protocol


class DocumentStoragePort(Protocol):
    def save(self, storage_key: str, content: bytes, content_type: str) -> str:
        """Persist file bytes and return the reference stored as documents.file_url."""
        ...
