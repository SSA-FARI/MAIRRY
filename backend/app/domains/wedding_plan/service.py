import uuid

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import AssetCategory, AssetOwnerType, WeddingPlanMemberRole
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.auth.service import DemoLoginService
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember
from app.domains.wedding_plan.repository import WeddingPlanRepository
from app.domains.wedding_plan.schemas import WeddingPlanRead, WeddingPlanUpsert


class WeddingPlanService:
    def __init__(self, session: Session, configuration: Settings) -> None:
        self._session = session
        self._configuration = configuration
        self._plans = WeddingPlanRepository(session)

    def upsert(self, payload: WeddingPlanUpsert) -> WeddingPlanRead:
        self._ensure_demo_user()
        try:
            self._plans.lock_user_plan(self._configuration.demo_user_id)
            plan = self._plans.get_current_for_user(self._configuration.demo_user_id)
            if plan is None:
                plan = self._create_plan(payload)
            else:
                plan.wedding_date = payload.wedding_date
                self._set_available_asset(plan.id, payload.available_asset)

            self._session.flush()
            response = self._to_response(plan)
            self._session.commit()
            return response
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="WeddingPlan을 저장하지 못했습니다.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

    def get_current(self) -> WeddingPlanRead:
        self._ensure_demo_user()
        try:
            plan = self._plans.get_current_for_user(self._configuration.demo_user_id)
            if plan is None:
                raise AppError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="현재 WeddingPlan이 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            return self._to_response(plan)
        except AppError:
            raise
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="WeddingPlan을 조회하지 못했습니다.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

    def _ensure_demo_user(self) -> None:
        DemoLoginService(self._session, self._configuration).login()

    def _create_plan(self, payload: WeddingPlanUpsert) -> WeddingPlan:
        plan = WeddingPlan(id=uuid.uuid4(), wedding_date=payload.wedding_date)
        self._plans.add_plan(plan)
        self._plans.add_member(
            WeddingPlanMember(
                id=uuid.uuid4(),
                wedding_plan_id=plan.id,
                user_id=self._configuration.demo_user_id,
                role=WeddingPlanMemberRole.OWNER,
            )
        )
        self._plans.add_asset(
            Asset(
                id=uuid.uuid4(),
                wedding_plan_id=plan.id,
                owner_member_id=None,
                owner_type=AssetOwnerType.JOINT,
                category=AssetCategory.CASH,
                amount=payload.available_asset,
                label=None,
            )
        )
        return plan

    def _set_available_asset(self, wedding_plan_id: uuid.UUID, amount: int) -> None:
        asset = self._plans.get_initial_asset(wedding_plan_id)
        if asset is None:
            self._plans.add_asset(
                Asset(
                    id=uuid.uuid4(),
                    wedding_plan_id=wedding_plan_id,
                    owner_member_id=None,
                    owner_type=AssetOwnerType.JOINT,
                    category=AssetCategory.CASH,
                    amount=amount,
                    label=None,
                )
            )
            return
        asset.amount = amount

    def _to_response(self, plan: WeddingPlan) -> WeddingPlanRead:
        if plan.wedding_date is None:
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="WeddingPlan 초기 설정이 완료되지 않았습니다.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return WeddingPlanRead(
            id=plan.id,
            wedding_date=plan.wedding_date,
            available_asset=self._plans.available_asset(plan.id),
        )
