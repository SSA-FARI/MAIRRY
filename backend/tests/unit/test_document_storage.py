import uuid
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.errors import AppError
from app.integrations.storage.document_storage import (
    MinioDocumentStorage,
    _build_client,
    _build_presigning_client,
    build_storage_key,
)


def test_build_storage_key_uses_document_id_and_lowercased_extension() -> None:
    document_id = uuid.uuid4()

    assert build_storage_key(document_id, "Contract.PDF") == f"{document_id}.pdf"


def test_build_storage_key_ignores_caller_supplied_filename() -> None:
    document_id = uuid.uuid4()

    key = build_storage_key(document_id, "../../etc/passwd.png")

    assert key == f"{document_id}.png"


def test_save_puts_object_in_private_bucket_and_returns_storage_key() -> None:
    client = Mock()
    storage = MinioDocumentStorage(client=client, bucket="mairry")

    result = storage.save("abc.pdf", b"%PDF-1.4", "application/pdf")

    assert result == "abc.pdf"
    client.put_object.assert_called_once_with(
        Bucket="mairry", Key="abc.pdf", Body=b"%PDF-1.4", ContentType="application/pdf"
    )


def test_save_wraps_client_error_as_storage_error_without_leaking_key() -> None:
    client = Mock()
    client.put_object.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}}, "PutObject"
    )
    storage = MinioDocumentStorage(client=client, bucket="mairry")

    with pytest.raises(AppError) as excinfo:
        storage.save("secret-key.pdf", b"content", "application/pdf")

    assert excinfo.value.status_code == 502
    assert excinfo.value.code.value == "STORAGE_ERROR"
    assert "secret-key" not in excinfo.value.message
    assert "secret-key" not in str(excinfo.value.details)


def test_build_client_is_cached_so_requests_share_one_connection_pool() -> None:
    assert _build_client() is _build_client()


def test_build_presigning_client_is_cached_so_requests_share_one_connection_pool() -> None:
    assert _build_presigning_client() is _build_presigning_client()


def test_read_returns_object_body_bytes() -> None:
    client = Mock()
    client.get_object.return_value = {"Body": BytesIO(b"%PDF-1.4")}
    storage = MinioDocumentStorage(client=client, bucket="mairry")

    result = storage.read("abc.pdf")

    assert result == b"%PDF-1.4"
    client.get_object.assert_called_once_with(Bucket="mairry", Key="abc.pdf")


def test_read_wraps_client_error_as_storage_error_without_leaking_key() -> None:
    client = Mock()
    client.get_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "boom"}}, "GetObject"
    )
    storage = MinioDocumentStorage(client=client, bucket="mairry")

    with pytest.raises(AppError) as excinfo:
        storage.read("secret-key.pdf")

    assert excinfo.value.status_code == 502
    assert excinfo.value.code.value == "STORAGE_ERROR"
    assert "secret-key" not in excinfo.value.message
    assert "secret-key" not in str(excinfo.value.details)


def test_build_preview_url_signs_against_bucket_and_key_with_configured_expiry() -> None:
    presigning_client = Mock()
    presigning_client.generate_presigned_url.return_value = "https://minio.example/signed"
    storage = MinioDocumentStorage(
        client=Mock(), bucket="mairry", presigning_client=presigning_client
    )

    before = datetime.now(UTC)
    url, expires_at = storage.build_preview_url("abc.pdf")
    after = datetime.now(UTC)

    assert url == "https://minio.example/signed"
    presigning_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "mairry", "Key": "abc.pdf"},
        ExpiresIn=settings.presigned_url_expiry_seconds,
    )
    expected_lower_bound = before.timestamp() + settings.presigned_url_expiry_seconds
    expected_upper_bound = after.timestamp() + settings.presigned_url_expiry_seconds
    assert expected_lower_bound <= expires_at.timestamp() <= expected_upper_bound


def test_build_preview_url_wraps_client_error_as_storage_error_without_leaking_key() -> None:
    presigning_client = Mock()
    presigning_client.generate_presigned_url.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}}, "GeneratePresignedUrl"
    )
    storage = MinioDocumentStorage(
        client=Mock(), bucket="mairry", presigning_client=presigning_client
    )

    with pytest.raises(AppError) as excinfo:
        storage.build_preview_url("secret-key.pdf")

    assert excinfo.value.status_code == 502
    assert excinfo.value.code.value == "STORAGE_ERROR"
    assert "secret-key" not in excinfo.value.message
    assert "secret-key" not in str(excinfo.value.details)
