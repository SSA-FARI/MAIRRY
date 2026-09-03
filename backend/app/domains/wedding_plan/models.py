import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import (
    AssetCategory,
    AssetOwnerType,
    WeddingPlanMemberRole,
    WeddingPlanStatus,
)


def _enum_values(enum_class: type) -> list[str]:
    return [member.value for member in enum_class]


class WeddingPlan(Base):
    __tablename__ = "wedding_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wedding_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[WeddingPlanStatus] = mapped_column(
        Enum(
            WeddingPlanStatus,
            name="wedding_plan_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=WeddingPlanStatus.ACTIVE,
        server_default=WeddingPlanStatus.ACTIVE.value,
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

    members: Mapped[list["WeddingPlanMember"]] = relationship(
        back_populates="wedding_plan", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="wedding_plan", cascade="all, delete-orphan"
    )


class WeddingPlanMember(Base):
    __tablename__ = "wedding_plan_members"
    __table_args__ = (
        UniqueConstraint(
            "wedding_plan_id",
            "user_id",
            name="uq_wedding_plan_members_plan_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wedding_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wedding_plans.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[WeddingPlanMemberRole] = mapped_column(
        Enum(
            WeddingPlanMemberRole,
            name="wedding_plan_member_role",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wedding_plan: Mapped[WeddingPlan] = relationship(back_populates="members")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_assets_amount_non_negative"),
        CheckConstraint(
            "(owner_type = 'PERSONAL' AND owner_member_id IS NOT NULL) OR "
            "(owner_type = 'JOINT' AND owner_member_id IS NULL)",
            name="ck_assets_owner_member",
        ),
        Index("ix_assets_wedding_plan_id", "wedding_plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wedding_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wedding_plans.id"), nullable=False
    )
    owner_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wedding_plan_members.id"), nullable=True
    )
    owner_type: Mapped[AssetOwnerType] = mapped_column(
        Enum(AssetOwnerType, name="asset_owner_type", values_callable=_enum_values),
        nullable=False,
    )
    category: Mapped[AssetCategory] = mapped_column(
        Enum(AssetCategory, name="asset_category", values_callable=_enum_values),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    wedding_plan: Mapped[WeddingPlan] = relationship(back_populates="assets")
