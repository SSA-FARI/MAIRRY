from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.integrations.storage.document_storage import _build_client, build_storage_key

pytestmark = pytest.mark.integration

_PDF_CONTENT = b"%PDF-1.4\n%mock wedding hall contract for storage access test\n"


@contextmanager
def _stored_object() -> Iterator[str]:
    storage_key = build_storage_key(uuid4(), "contract.pdf")
    client = _build_client()
    client.put_object(
        Bucket=settings.object_storage_bucket,
        Key=storage_key,
        Body=_PDF_CONTENT,
        ContentType="application/pdf",
    )
    try:
        yield storage_key
    finally:
        try:
            client.delete_object(Bucket=settings.object_storage_bucket, Key=storage_key)
        except ClientError:
            pass


def test_stored_object_rejects_anonymous_direct_access() -> None:
    """The bucket is set to `mc anonymous set none` in compose.yaml so that documents are
    only reachable through the backend. An unauthenticated GET straight at the object URL
    must therefore be denied instead of returning the file bytes."""
    with _stored_object() as storage_key:
        object_url = (
            f"{settings.object_storage_endpoint}/{settings.object_storage_bucket}/{storage_key}"
        )

        response = httpx.get(object_url)

        assert response.status_code in (403, 404)
        assert response.content != _PDF_CONTENT


def test_bucket_rejects_anonymous_listing() -> None:
    """Anonymous ListBucket must be denied too, otherwise storage keys (and therefore every
    document's contents) could be enumerated without ever calling the backend API."""
    response = httpx.get(f"{settings.object_storage_endpoint}/{settings.object_storage_bucket}/")

    assert response.status_code in (403, 404)
