import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from ai.common.exceptions import DemoFallbackError
from ai.document_extraction.fallback import (
    DEFAULT_DEMO_DOCUMENT_PATH,
    DEFAULT_DEMO_DOCUMENT_SHA256,
    DEFAULT_DEMO_FALLBACK_REGISTRY,
    DemoFallbackEntry,
    DemoFallbackRegistry,
    calculate_file_sha256,
    load_fallback,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXTRACTION_SCHEMA_PATH = REPOSITORY_ROOT / "contracts" / "ai-extraction.schema.json"


def test_demo_document_hash_is_pinned() -> None:
    assert calculate_file_sha256(DEFAULT_DEMO_DOCUMENT_PATH) == DEFAULT_DEMO_DOCUMENT_SHA256


def test_registered_demo_fallback_matches_the_extraction_contract() -> None:
    extraction = DEFAULT_DEMO_FALLBACK_REGISTRY.find(DEFAULT_DEMO_DOCUMENT_PATH)

    assert extraction is not None
    schema = json.loads(EXTRACTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        extraction.model_dump(mode="json")
    )


def test_same_filename_with_different_content_does_not_match(tmp_path: Path) -> None:
    changed_document = tmp_path / DEFAULT_DEMO_DOCUMENT_PATH.name
    changed_document.write_bytes(DEFAULT_DEMO_DOCUMENT_PATH.read_bytes() + b"changed")

    assert DEFAULT_DEMO_FALLBACK_REGISTRY.find(changed_document) is None


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        json.dumps(
            {
                "documentType": "WEDDING_HALL",
                "company": "A웨딩홀",
                "totalPrice": -1,
                "payments": [],
                "cancellationTerms": [],
                "warnings": [],
            }
        ),
    ],
)
def test_invalid_fallback_payload_is_rejected(tmp_path: Path, payload: str) -> None:
    fallback_path = tmp_path / "invalid-extraction.json"
    fallback_path.write_text(payload, encoding="utf-8")

    with pytest.raises(DemoFallbackError, match="registered demo fallback is invalid"):
        load_fallback(fallback_path)


def test_duplicate_demo_hash_is_rejected() -> None:
    entry = DemoFallbackEntry(
        document_sha256=DEFAULT_DEMO_DOCUMENT_SHA256,
        extraction_path=Path("first.json"),
    )

    with pytest.raises(ValueError, match="duplicate demo document hash"):
        DemoFallbackRegistry((entry, entry))
