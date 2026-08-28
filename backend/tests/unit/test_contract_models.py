from sqlalchemy import BigInteger, CheckConstraint, UniqueConstraint

from app.domains.contracts.models import CancellationTerm, Contract, Payment


def test_contract_model_matches_confirmed_contract_constraints() -> None:
    table = Contract.__table__

    assert table.c.document_id.nullable is False
    assert table.c.document_id.unique is True
    assert table.c.total_price.nullable is False
    assert isinstance(table.c.total_price.type, BigInteger)
    assert table.c.confirmed_by_member_id.nullable is True
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_contracts_total_price_non_negative"
        for constraint in table.constraints
    )


def test_payment_model_requires_non_negative_amount_and_allows_nullable_evidence() -> None:
    table = Payment.__table__

    assert table.c.amount.nullable is False
    assert isinstance(table.c.amount.type, BigInteger)
    assert table.c.due_date.nullable is True
    assert table.c.source_text.nullable is True
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_payments_amount_non_negative"
        for constraint in table.constraints
    )


def test_contract_children_use_database_cascade_foreign_keys() -> None:
    for table in (Payment.__table__, CancellationTerm.__table__):
        foreign_key = next(iter(table.c.contract_id.foreign_keys))
        assert foreign_key.target_fullname == "contracts.id"
        assert foreign_key.ondelete == "CASCADE"


def test_contract_document_is_one_to_one_and_restricts_document_deletion() -> None:
    table = Contract.__table__
    foreign_key = next(iter(table.c.document_id.foreign_keys))

    assert foreign_key.target_fullname == "documents.id"
    assert foreign_key.ondelete == "RESTRICT"
    assert table.c.document_id.unique or any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("document_id",)
        for constraint in table.constraints
    )
