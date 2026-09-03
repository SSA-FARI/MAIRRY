from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.errors import AppError
from app.domains.wedding_plan.models import WeddingPlan
from app.domains.wedding_plan.repository import WeddingPlanRepository
from app.domains.wedding_plan.schemas import WeddingPlanUpsert
from app.domains.wedding_plan.service import WeddingPlanService


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        demo_user_id=uuid4(),
        demo_user_login_id="demo",
        demo_user_display_name="Demo User",
        demo_user_email=None,
    )


def test_member_insert_failure_rolls_back_entire_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    service = WeddingPlanService(session, _settings())
    monkeypatch.setattr(service, "_ensure_demo_user", lambda: None)
    monkeypatch.setattr(WeddingPlanRepository, "lock_user_plan", lambda self, user_id: None)
    monkeypatch.setattr(WeddingPlanRepository, "get_current_for_user", lambda self, user_id: None)

    def fail_member_insert(self, member) -> None:
        raise SQLAlchemyError("member insert failed")

    monkeypatch.setattr(WeddingPlanRepository, "add_member", fail_member_insert)

    try:
        service.upsert(WeddingPlanUpsert(weddingDate="2027-05-15", availableAsset=30_000_000))
    except AppError as error:
        assert error.status_code == 500
    else:
        raise AssertionError("AppError was not raised")

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    ("initial_asset", "expected_amount"),
    [(SimpleNamespace(amount=40_000_000), 40_000_000), (None, 0)],
)
def test_response_uses_only_initial_asset(initial_asset: object, expected_amount: int) -> None:
    service = WeddingPlanService(MagicMock(), _settings())
    service._plans = MagicMock()
    service._plans.get_initial_asset.return_value = initial_asset
    service._plans.available_asset.return_value = 55_000_000
    plan = WeddingPlan(id=uuid4(), wedding_date=date(2027, 5, 15))

    response = service._to_response(plan)

    assert response.available_asset == expected_amount
    service._plans.available_asset.assert_not_called()
