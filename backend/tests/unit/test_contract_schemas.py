from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.contracts.schemas import ContractDetailRead, ContractListRead


def test_contract_list_serializes_openapi_field_names() -> None:
    contract_id = uuid4()
    response = ContractListRead.model_validate(
        {
            "items": [
                {
                    "id": contract_id,
                    "company": "A웨딩홀",
                    "totalPrice": 23_000_000,
                    "status": "CONFIRMED",
                    "nextPayment": {
                        "contractId": contract_id,
                        "company": "A웨딩홀",
                        "name": "잔금",
                        "amount": 20_000_000,
                        "dueDate": "2027-04-30",
                    },
                }
            ]
        }
    )

    payload = response.model_dump(mode="json", by_alias=True)

    assert payload["items"][0]["totalPrice"] == 23_000_000
    assert payload["items"][0]["nextPayment"]["dueDate"] == "2027-04-30"
    assert "total_price" not in payload["items"][0]


def test_contract_detail_preserves_nullable_dates_and_evidence() -> None:
    response = ContractDetailRead(
        id=uuid4(),
        document_id=uuid4(),
        document_type="WEDDING_HALL",
        company="A웨딩홀",
        total_price=23_000_000,
        status="CONFIRMED",
        payments=[
            {
                "name": "잔금",
                "amount": 20_000_000,
                "due_date": None,
                "status": "UNPAID",
                "source_text": None,
            }
        ],
        cancellation_terms=[{"summary": "직접 입력", "source_text": None}],
    )

    payload = response.model_dump(mode="json", by_alias=True)

    assert payload["payments"][0]["dueDate"] is None
    assert payload["payments"][0]["sourceText"] is None
    assert payload["cancellationTerms"][0]["sourceText"] is None


def test_contract_detail_requires_at_least_one_payment() -> None:
    with pytest.raises(ValidationError):
        ContractDetailRead(
            id=uuid4(),
            document_id=uuid4(),
            document_type="WEDDING_HALL",
            company="A웨딩홀",
            total_price=23_000_000,
            status="CONFIRMED",
            payments=[],
            cancellation_terms=[],
        )


def test_upcoming_payment_uses_date_type() -> None:
    response = ContractListRead.model_validate(
        {
            "items": [
                {
                    "id": uuid4(),
                    "company": "A웨딩홀",
                    "totalPrice": 23_000_000,
                    "status": "CONFIRMED",
                    "nextPayment": None,
                }
            ]
        }
    )

    assert response.items[0].next_payment is None
    assert date.fromisoformat("2027-04-30") == date(2027, 4, 30)
