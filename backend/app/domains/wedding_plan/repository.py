from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetCategory, AssetOwnerType, WeddingPlanStatus
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember


class WeddingPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_user_plan(self, user_id: UUID) -> None:
        """Serialize a user's upserts without changing the ERD's N:M cardinality."""
        self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(user_id)))))

    def get_current_for_user(self, user_id: UUID) -> WeddingPlan | None:
        statement = (
            select(WeddingPlan)
            .join(WeddingPlanMember)
            .where(
                WeddingPlanMember.user_id == user_id,
                WeddingPlan.status == WeddingPlanStatus.ACTIVE,
            )
            .order_by(WeddingPlanMember.joined_at, WeddingPlanMember.id)
            .limit(1)
        )
        return self._session.scalar(statement)

    def add_plan(self, plan: WeddingPlan) -> None:
        self._session.add(plan)

    def add_member(self, member: WeddingPlanMember) -> None:
        self._session.add(member)

    def get_initial_asset(self, wedding_plan_id: UUID) -> Asset | None:
        statement = (
            select(Asset)
            .where(
                Asset.wedding_plan_id == wedding_plan_id,
                Asset.owner_type == AssetOwnerType.JOINT,
                Asset.category == AssetCategory.CASH,
                Asset.owner_member_id.is_(None),
            )
            .order_by(Asset.created_at, Asset.id)
            .limit(1)
        )
        return self._session.scalar(statement)

    def add_asset(self, asset: Asset) -> None:
        self._session.add(asset)

    def available_asset(self, wedding_plan_id: UUID) -> int:
        """Return the sum of every asset in a plan for finance calculations."""
        statement = select(func.coalesce(func.sum(Asset.amount), 0)).where(
            Asset.wedding_plan_id == wedding_plan_id
        )
        return int(self._session.scalar(statement) or 0)
