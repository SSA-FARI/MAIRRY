import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import AnalysisSource, DocumentStatus


class Document(Base):
    """원본 계약서/견적서 파일과 AI 최초 분석 결과. docs/06_ERD.md `documents` 참고."""

    __tablename__ = "documents"
    __table_args__ = (
        Index(
            "ix_documents_wedding_plan_id_analysis_status_created_at",
            "wedding_plan_id",
            "analysis_status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # TODO: wedding_plans / wedding_plan_members(A 담당, app/domains/wedding_plan/models.py)가
    # main에 merge되면 별도 마이그레이션에서 이 두 컬럼에 FK 제약을 추가한다.
    wedding_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uploaded_by_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extraction_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analysis_status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
    )
    analysis_source: Mapped[AnalysisSource] = mapped_column(
        Enum(
            AnalysisSource,
            name="analysis_source",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=AnalysisSource.LIVE_AI,
        server_default=AnalysisSource.LIVE_AI.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
