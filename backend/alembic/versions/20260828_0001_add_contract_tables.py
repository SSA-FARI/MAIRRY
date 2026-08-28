"""Add contract, payment, and cancellation term tables.

Revision ID: 20260828_0001
Revises: 20260827_0001
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260828_0001"
down_revision: str | Sequence[str] | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_type_enum = postgresql.ENUM("WEDDING_HALL", "UNKNOWN", name="document_type")
contract_status_enum = postgresql.ENUM("CONFIRMED", name="contract_status")
payment_status_enum = postgresql.ENUM("PAID", "UNPAID", "UNKNOWN", name="payment_status")


def upgrade() -> None:
    bind = op.get_bind()
    document_type_enum.create(bind, checkfirst=True)
    contract_status_enum.create(bind, checkfirst=True)
    payment_status_enum.create(bind, checkfirst=True)
    document_type_enum.create_type = False
    contract_status_enum.create_type = False
    payment_status_enum.create_type = False

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # TODO: wedding_plans / wedding_plan_members가 병합되면 FK를 추가한다.
        sa.Column("wedding_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("document_type", document_type_enum, nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("total_price", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            contract_status_enum,
            nullable=False,
            server_default="CONFIRMED",
        ),
        sa.Column("confirmed_by_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("total_price >= 0", name="ck_contracts_total_price_non_negative"),
    )
    op.create_index(
        "ix_contracts_wedding_plan_id_status_confirmed_at",
        "contracts",
        ["wedding_plan_id", "status", "confirmed_at"],
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            payment_status_enum,
            nullable=False,
            server_default="UNPAID",
        ),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
    )
    op.create_index(
        "ix_payments_contract_id_status_due_date",
        "payments",
        ["contract_id", "status", "due_date"],
    )

    op.create_table(
        "cancellation_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_cancellation_terms_contract_id", "cancellation_terms", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_cancellation_terms_contract_id", table_name="cancellation_terms")
    op.drop_table("cancellation_terms")
    op.drop_index("ix_payments_contract_id_status_due_date", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_contracts_wedding_plan_id_status_confirmed_at", table_name="contracts")
    op.drop_table("contracts")
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
    contract_status_enum.drop(op.get_bind(), checkfirst=True)
    document_type_enum.drop(op.get_bind(), checkfirst=True)
