from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.enums import ContractStatus, DocumentStatus, DocumentType, PaymentStatus
from app.core.errors import AppError
from app.domains.contracts.models import CancellationTerm, Contract, Payment
from app.domains.contracts.schemas import ContractConfirm
from app.domains.contracts.service import ContractConfirmationService, ContractQueryService


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        demo_user_id=uuid4(),
        demo_user_login_id="demo",
        demo_user_display_name="Demo User",
        demo_user_email=None,
    )


def _payment(
    *,
    name: str,
    due_date: date | None,
    status: PaymentStatus,
    source_text: str | None = None,
) -> Payment:
    return Payment(
        id=uuid4(),
        name=name,
        amount=1_000_000,
        due_date=due_date,
        status=status,
        source_text=source_text,
    )


def _contract(*, payments: list[Payment]) -> Contract:
    return Contract(
        id=uuid4(),
        wedding_plan_id=uuid4(),
        document_id=uuid4(),
        document_type=DocumentType.WEDDING_HALL,
        company="A웨딩홀",
        total_price=23_000_000,
        status=ContractStatus.CONFIRMED,
        confirmed_at=datetime(2026, 9, 1, tzinfo=UTC),
        payments=payments,
        cancellation_terms=[],
    )


def _service() -> ContractQueryService:
    service = ContractQueryService(
        MagicMock(),
        _settings(),
        today_provider=lambda: date(2027, 1, 1),
    )
    service._plans = MagicMock()
    service._contracts = MagicMock()
    return service


def test_list_without_current_plan_returns_empty_items() -> None:
    service = _service()
    service._plans.get_current_for_user.return_value = None

    response = service.list_contracts()

    assert response.items == []
    service._contracts.list_confirmed.assert_not_called()


def test_list_selects_nearest_future_unpaid_payment() -> None:
    service = _service()
    plan_id = uuid4()
    contract = _contract(
        payments=[
            _payment(name="완료 계약금", due_date=date(2027, 1, 2), status=PaymentStatus.PAID),
            _payment(name="지난 잔금", due_date=date(2026, 12, 31), status=PaymentStatus.UNPAID),
            _payment(name="날짜 미정", due_date=None, status=PaymentStatus.UNPAID),
            _payment(name="중도금", due_date=date(2027, 3, 1), status=PaymentStatus.UNPAID),
            _payment(name="잔금", due_date=date(2027, 4, 30), status=PaymentStatus.UNPAID),
        ]
    )
    service._plans.get_current_for_user.return_value = SimpleNamespace(id=plan_id)
    service._contracts.list_confirmed.return_value = [contract]

    response = service.list_contracts()

    next_payment = response.items[0].next_payment
    assert next_payment is not None
    assert next_payment.name == "중도금"
    assert next_payment.due_date == date(2027, 3, 1)
    assert next_payment.contract_id == contract.id


def test_detail_sorts_payments_and_preserves_nullable_evidence() -> None:
    service = _service()
    plan_id = uuid4()
    undated = _payment(
        name="날짜 미정",
        due_date=None,
        status=PaymentStatus.UNPAID,
        source_text=None,
    )
    dated = _payment(
        name="계약금",
        due_date=date(2027, 1, 2),
        status=PaymentStatus.PAID,
        source_text="계약금 100만 원",
    )
    contract = _contract(payments=[undated, dated])
    contract.cancellation_terms = [
        CancellationTerm(
            id=uuid4(),
            summary="직접 입력",
            source_text=None,
            created_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
    ]
    service._plans.get_current_for_user.return_value = SimpleNamespace(id=plan_id)
    service._contracts.get_confirmed.return_value = contract

    response = service.get_contract(contract.id)

    assert [payment.name for payment in response.payments] == ["계약금", "날짜 미정"]
    assert response.payments[1].source_text is None
    assert response.cancellation_terms[0].source_text is None
    service._contracts.get_confirmed.assert_called_once_with(plan_id, contract.id)


def test_detail_returns_same_404_for_missing_plan_or_contract() -> None:
    service = _service()
    service._plans.get_current_for_user.return_value = None

    with pytest.raises(AppError) as raised:
        service.get_contract(uuid4())

    assert raised.value.status_code == 404
    assert raised.value.details == {}
    service._contracts.get_confirmed.assert_not_called()


def test_repository_failure_rolls_back_and_returns_sanitized_error() -> None:
    session = MagicMock()
    service = ContractQueryService(session, _settings())
    service._plans = MagicMock()
    service._plans.get_current_for_user.side_effect = SQLAlchemyError("sensitive db detail")

    with pytest.raises(AppError) as raised:
        service.list_contracts()

    assert raised.value.status_code == 500
    assert "sensitive" not in raised.value.message
    assert raised.value.details == {}
    session.rollback.assert_called_once_with()


def test_confirmation_persistence_failure_rolls_back() -> None:
    session = MagicMock()
    service = ContractConfirmationService(session, _settings())
    plan = SimpleNamespace(id=uuid4())
    member = SimpleNamespace(id=uuid4())
    document = SimpleNamespace(
        id=uuid4(),
        document_type=None,
        analysis_status=DocumentStatus.REVIEW_REQUIRED,
    )
    service._plans = MagicMock()
    service._plans.get_current_for_user.return_value = plan
    service._plans.get_member_for_user.return_value = member
    service._documents = MagicMock()
    service._documents.get_by_id.return_value = document
    service._contracts = MagicMock()
    service._contracts.add.side_effect = SQLAlchemyError("sensitive db detail")
    payload = ContractConfirm.model_validate(
        {
            "documentType": "WEDDING_HALL",
            "company": "A웨딩홀",
            "totalPrice": 23_000_000,
            "payments": [
                {
                    "name": "잔금",
                    "amount": 20_000_000,
                    "dueDate": None,
                    "status": "UNPAID",
                    "sourceText": None,
                }
            ],
            "cancellationTerms": [],
        }
    )

    with pytest.raises(AppError) as raised:
        service.confirm(document.id, payload)

    assert raised.value.status_code == 500
    assert "sensitive" not in raised.value.message
    session.rollback.assert_called_once_with()
