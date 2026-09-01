"""Add contract wedding plan and member foreign keys.

Revision ID: 20260901_0001
Revises: 20260828_0002
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260901_0001"
down_revision: str | Sequence[str] | None = "20260828_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy demo rows can still reference the former fixed IDs. PostgreSQL NOT VALID
    # keeps those rows readable while enforcing both constraints for every new write.
    op.create_foreign_key(
        "fk_contracts_wedding_plan_id_wedding_plans",
        "contracts",
        "wedding_plans",
        ["wedding_plan_id"],
        ["id"],
        ondelete="RESTRICT",
        postgresql_not_valid=True,
    )
    op.create_foreign_key(
        "fk_contracts_confirmed_by_member_id_wedding_plan_members",
        "contracts",
        "wedding_plan_members",
        ["confirmed_by_member_id"],
        ["id"],
        ondelete="RESTRICT",
        postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_contracts_confirmed_by_member_id_wedding_plan_members",
        "contracts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_contracts_wedding_plan_id_wedding_plans",
        "contracts",
        type_="foreignkey",
    )
