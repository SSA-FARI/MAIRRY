import uuid
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.core.errors import AppError
from app.integrations.storage.document_storage import MinioDocumentStorage, build_storage_key


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
