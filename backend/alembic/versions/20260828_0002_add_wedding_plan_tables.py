"""Add wedding plan, membership, and asset tables.

Revision ID: 20260828_0002
Revises: 20260827_0002
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260828_0002"
down_revision: str | Sequence[str] | None = "20260827_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

wedding_plan_status_enum = postgresql.ENUM(
    "ACTIVE", "COMPLETED", name="wedding_plan_status"
)
wedding_plan_member_role_enum = postgresql.ENUM(
    "OWNER", "PARTNER", name="wedding_plan_member_role"
)
asset_owner_type_enum = postgresql.ENUM("PERSONAL", "JOINT", name="asset_owner_type")
asset_category_enum = postgresql.ENUM("CASH", "SAVINGS", name="asset_category")


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        wedding_plan_status_enum,
        wedding_plan_member_role_enum,
        asset_owner_type_enum,
        asset_category_enum,
    ):
        enum_type.create(bind, checkfirst=True)
        enum_type.create_type = False

    op.create_table(
        "wedding_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wedding_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            wedding_plan_status_enum,
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wedding_plan_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wedding_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", wedding_plan_member_role_enum, nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["wedding_plan_id"], ["wedding_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wedding_plan_id",
            "user_id",
            name="uq_wedding_plan_members_plan_user",
        ),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wedding_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_type", asset_owner_type_enum, nullable=False),
        sa.Column("category", asset_category_enum, nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount >= 0", name="ck_assets_amount_non_negative"),
        sa.CheckConstraint(
            "(owner_type = 'PERSONAL' AND owner_member_id IS NOT NULL) OR "
            "(owner_type = 'JOINT' AND owner_member_id IS NULL)",
            name="ck_assets_owner_member",
        ),
        sa.ForeignKeyConstraint(["owner_member_id"], ["wedding_plan_members.id"]),
        sa.ForeignKeyConstraint(["wedding_plan_id"], ["wedding_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_wedding_plan_id", "assets", ["wedding_plan_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_wedding_plan_id", table_name="assets")
    op.drop_table("assets")
    op.drop_table("wedding_plan_members")
    op.drop_table("wedding_plans")
    asset_category_enum.drop(op.get_bind(), checkfirst=True)
    asset_owner_type_enum.drop(op.get_bind(), checkfirst=True)
    wedding_plan_member_role_enum.drop(op.get_bind(), checkfirst=True)
    wedding_plan_status_enum.drop(op.get_bind(), checkfirst=True)
