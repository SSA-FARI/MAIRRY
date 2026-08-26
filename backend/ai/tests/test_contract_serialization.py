from datetime import UTC, date, datetime

from ai.common.types import ToolResultView
from ai.document_extraction.schemas import DocumentExtraction, ExtractedPayment


def test_tool_result_serializes_contract_fields_as_camel_case() -> None:
    result = ToolResultView(
        status="SUCCESS",
        tool_name="getFinanceSummary",
        data={"expectedBalance": 10_000_000},
        evidence=[],
        calculated_at=datetime(2026, 8, 26, 3, 0, tzinfo=UTC),
        error=None,
    )

    payload = result.model_dump(mode="json")

    assert payload["toolName"] == "getFinanceSummary"
    assert payload["calculatedAt"] == "2026-08-26T03:00:00Z"
    assert "tool_name" not in payload
    assert "calculated_at" not in payload


def test_document_extraction_accepts_and_serializes_camel_case_contract() -> None:
    extraction = DocumentExtraction.model_validate(
        {
            "documentType": "WEDDING_HALL",
            "company": "A웨딩홀",
            "totalPrice": 23_000_000,
            "payments": [
                {
                    "name": "잔금",
                    "amount": 20_000_000,
                    "dueDate": "2027-04-30",
                    "status": "UNPAID",
                    "sourceText": "잔금 20,000,000원",
                }
            ],
            "cancellationTerms": [],
            "warnings": [],
        }
    )

    assert extraction.document_type == "WEDDING_HALL"
    assert extraction.payments[0].due_date == date(2027, 4, 30)

    payload = extraction.model_dump(mode="json")
    assert payload["documentType"] == "WEDDING_HALL"
    assert payload["totalPrice"] == 23_000_000
    assert payload["payments"][0]["dueDate"] == "2027-04-30"
    assert payload["payments"][0]["sourceText"] == "잔금 20,000,000원"
    assert "document_type" not in payload


def test_document_extraction_still_accepts_python_field_names() -> None:
    extraction = DocumentExtraction(
        document_type="UNKNOWN",
        company=None,
        total_price=None,
        payments=[
            ExtractedPayment(
                name="계약금",
                amount=None,
                due_date=None,
                status="UNKNOWN",
                source_text="",
            )
        ],
        cancellation_terms=[],
        warnings=["확인이 필요합니다."],
    )

    assert extraction.document_type == "UNKNOWN"
