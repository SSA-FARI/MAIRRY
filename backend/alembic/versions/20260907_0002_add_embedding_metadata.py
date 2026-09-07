"""Track the embedding model, version, and vector dimension.

Revision ID: 20260907_0002
Revises: 20260907_0001
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0002"
down_revision: str | Sequence[str] | None = "20260907_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "document_chunks",
        "chunk_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_model",
            sa.String(length=100),
            nullable=False,
            server_default="legacy-hashing-384",
        ),
    )
    op.add_column("document_chunks", sa.Column("source", sa.String(length=100), nullable=True))
    op.add_column(
        "document_chunks", sa.Column("dataset_record_id", sa.String(length=150), nullable=True)
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_version", sa.String(length=32), nullable=False, server_default="v1"),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="384"),
    )
    op.alter_column("document_chunks", "embedding_model", server_default=None)
    op.alter_column("document_chunks", "embedding_version", server_default=None)
    op.alter_column("document_chunks", "embedding_dimensions", server_default=None)
    op.create_index(
        "ix_document_chunks_embedding_profile",
        "document_chunks",
        ["embedding_model", "embedding_version", "embedding_dimensions", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_profile", table_name="document_chunks")
    op.drop_column("document_chunks", "embedding_dimensions")
    op.drop_column("document_chunks", "embedding_version")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "chunk_metadata")
    op.drop_column("document_chunks", "dataset_record_id")
    op.drop_column("document_chunks", "source")
    op.alter_column(
        "document_chunks",
        "chunk_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
