from typing import Protocol


class DocumentStoragePort(Protocol):
    def save(self, storage_key: str, content: bytes, content_type: str) -> str:
        """Persist file bytes and return the reference stored as documents.file_url."""
        ...

    def read(self, storage_key: str) -> bytes:
        """Fetch the original file bytes for the given documents.file_url reference."""
        ...
