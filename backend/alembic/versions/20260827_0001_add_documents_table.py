"""Add documents table.

Revision ID: 20260827_0001
Revises: 20260826_0001
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260827_0001"
down_revision: str | Sequence[str] | None = "20260826_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_status_enum = postgresql.ENUM(
    "UPLOADED",
    "PROCESSING",
    "REVIEW_REQUIRED",
    "FAILED",
    "CONFIRMED",
    name="document_status",
)
analysis_source_enum = postgresql.ENUM(
    "LIVE_AI",
    "DEMO_FALLBACK",
    name="analysis_source",
)


def upgrade() -> None:
    bind = op.get_bind()
    document_status_enum.create(bind, checkfirst=True)
    analysis_source_enum.create(bind, checkfirst=True)
    # Types are created explicitly above; stop create_table from re-issuing CREATE TYPE.
    document_status_enum.create_type = False
    analysis_source_enum.create_type = False

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # wedding_plans / wedding_plan_members는 A 담당 마이그레이션에서 추가된다.
        # 마이그레이션 head를 머지할 때 이 FK보다 먼저 적용되도록 순서를 맞춘다.
        sa.Column(
            "wedding_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wedding_plans.id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wedding_plan_members.id"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("extraction_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "analysis_status",
            document_status_enum,
            nullable=False,
            server_default="UPLOADED",
        ),
        sa.Column(
            "analysis_source",
            analysis_source_enum,
            nullable=False,
            server_default="LIVE_AI",
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
    )
    op.create_index(
        "ix_documents_wedding_plan_id_analysis_status_created_at",
        "documents",
        ["wedding_plan_id", "analysis_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_documents_wedding_plan_id_analysis_status_created_at",
        table_name="documents",
    )
    op.drop_table("documents")
    analysis_source_enum.drop(op.get_bind(), checkfirst=True)
    document_status_enum.drop(op.get_bind(), checkfirst=True)
