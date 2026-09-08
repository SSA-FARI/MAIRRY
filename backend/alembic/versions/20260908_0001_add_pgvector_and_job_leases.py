"""Add DB-side vector search and durable RAG job leases.

Revision ID: 20260908_0001
Revises: 20260907_0003
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision: str = "20260908_0001"
down_revision: str | Sequence[str] | None = "20260907_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "document_chunks",
        sa.Column("embedding_vector", VECTOR(1536), nullable=True),
    )
    # Preserve JSONB and only copy rows that match the deployed 1536-dimensional profile.
    # Incompatible rows remain available for an explicit re-index instead of being deleted.
    op.execute(
        """
        UPDATE document_chunks
        SET embedding_vector = embedding::text::vector(1536)
        WHERE embedding_dimensions = 1536
          AND jsonb_typeof(embedding) = 'array'
          AND jsonb_array_length(embedding) = 1536
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_array_elements(embedding) AS element(value)
              WHERE jsonb_typeof(value) <> 'number'
          )
        """
    )
    op.add_column(
        "rag_index_jobs",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "rag_index_jobs",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_rag_index_jobs_reconciliation",
        "rag_index_jobs",
        ["status", "next_attempt_at", "locked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rag_index_jobs_reconciliation", table_name="rag_index_jobs")
    op.drop_column("rag_index_jobs", "next_attempt_at")
    op.drop_column("rag_index_jobs", "locked_at")
    op.drop_column("document_chunks", "embedding_vector")
