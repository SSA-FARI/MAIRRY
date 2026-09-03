import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.errors import AppError


def build_storage_key(document_id: uuid.UUID, original_filename: str) -> str:
    """Derive a private-bucket object key that never reuses the caller-supplied filename."""
    extension = Path(original_filename).suffix.lower()
    return f"{document_id}{extension}"


@lru_cache(maxsize=1)
def _build_client() -> Any:
    """Cached so every request-scoped MinioDocumentStorage reuses one connection pool."""
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache(maxsize=1)
def _build_presigning_client() -> Any:
    """Separate client signed against the browser-reachable endpoint. generate_presigned_url()
    never makes a network call, so this client's endpoint only has to match what the viewer can
    open (which differs from the backend-to-storage endpoint inside Docker Compose)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_public_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class MinioDocumentStorage:
    """Private-bucket S3-compatible adapter backing documents.file_url (no public URLs)."""

    def __init__(
        self,
        client: Any | None = None,
        bucket: str | None = None,
        presigning_client: Any | None = None,
    ) -> None:
        self._client = client if client is not None else _build_client()
        self._bucket = bucket if bucket is not None else settings.object_storage_bucket
        self._presigning_client = (
            presigning_client if presigning_client is not None else _build_presigning_client()
        )

    def save(self, storage_key: str, content: bytes, content_type: str) -> str:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=storage_key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                message="파일을 저장하지 못했습니다.",
                status_code=502,
            ) from exc
        return storage_key

    def read(self, storage_key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=storage_key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                message="파일을 불러오지 못했습니다.",
                status_code=502,
            ) from exc

    def build_preview_url(self, storage_key: str) -> tuple[str, datetime]:
        expires_in = settings.presigned_url_expiry_seconds
        try:
            url = self._presigning_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": storage_key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                message="원문 미리보기 URL을 발급하지 못했습니다.",
                status_code=502,
            ) from exc
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        return url, expires_at
