from pathlib import Path

from fastapi import UploadFile

from app.core.error_codes import ErrorCode
from app.core.errors import AppError

_CHUNK_SIZE_BYTES = 1024 * 1024

_ALLOWED_CONTENT_TYPES_BY_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

_SIGNATURES_BY_CONTENT_TYPE: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def resolve_expected_content_type(filename: str) -> str:
    """Map the upload's extension to the MIME type it must match, or raise 415."""
    extension = Path(filename).suffix.lower()
    content_type = _ALLOWED_CONTENT_TYPES_BY_EXTENSION.get(extension)
    if content_type is None:
        raise AppError(
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message="PDF, JPG, PNG 파일만 업로드할 수 있습니다.",
            status_code=415,
            details={"allowedExtensions": sorted(_ALLOWED_CONTENT_TYPES_BY_EXTENSION)},
        )
    return content_type


def ensure_signature_matches(content: bytes, expected_content_type: str) -> None:
    """Reject a file whose actual bytes don't match its extension's MIME signature."""
    signatures = _SIGNATURES_BY_CONTENT_TYPE[expected_content_type]
    if not any(content.startswith(signature) for signature in signatures):
        raise AppError(
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message="파일 내용이 확장자와 일치하지 않습니다.",
            status_code=415,
            details={"expectedContentType": expected_content_type},
        )


async def read_upload_within_limit(file: UploadFile, max_size_bytes: int) -> bytes:
    """Read the upload in chunks, aborting with 413 as soon as the limit is exceeded."""
    buffer = bytearray()
    while chunk := await file.read(_CHUNK_SIZE_BYTES):
        buffer.extend(chunk)
        if len(buffer) > max_size_bytes:
            raise AppError(
                code=ErrorCode.FILE_TOO_LARGE,
                message=f"파일 용량은 {max_size_bytes // (1024 * 1024)}MB 이하여야 합니다.",
                status_code=413,
                details={"maxSizeBytes": max_size_bytes},
            )
    return bytes(buffer)
