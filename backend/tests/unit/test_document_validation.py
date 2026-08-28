import pytest

from app.core.errors import AppError
from app.domains.documents.validation import (
    ensure_signature_matches,
    resolve_expected_content_type,
)


def test_resolve_expected_content_type_accepts_supported_extensions() -> None:
    assert resolve_expected_content_type("contract.pdf") == "application/pdf"
    assert resolve_expected_content_type("contract.PNG") == "image/png"
    assert resolve_expected_content_type("contract.jpeg") == "image/jpeg"


def test_resolve_expected_content_type_rejects_unsupported_extension() -> None:
    with pytest.raises(AppError) as excinfo:
        resolve_expected_content_type("contract.docx")

    assert excinfo.value.status_code == 415
    assert excinfo.value.code.value == "UNSUPPORTED_MEDIA_TYPE"


def test_ensure_signature_matches_accepts_matching_pdf_bytes() -> None:
    ensure_signature_matches(b"%PDF-1.4 ...", "application/pdf")


def test_ensure_signature_matches_rejects_mismatched_bytes() -> None:
    with pytest.raises(AppError) as excinfo:
        ensure_signature_matches(b"not actually a pdf", "application/pdf")

    assert excinfo.value.status_code == 415
