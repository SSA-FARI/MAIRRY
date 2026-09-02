from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.application.demo_seed import (
    DEMO_HALL_BALANCE_ID,
    DEMO_HALL_DEPOSIT_ID,
    DEMO_STUDIO_BALANCE_ID,
    DEMO_STUDIO_DEPOSIT_ID,
    payment_seeds,
    seed_demo_data,
)
from app.core.config import Settings
from app.core.enums import PaymentStatus
from app.domains.contracts.models import Contract, Payment
from app.domains.documents.models import Document
from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember


def test_demo_payment_seed_has_stable_ids_and_realistic_statuses() -> None:
    today = date(2026, 9, 1)

    payments = payment_seeds(today)

    assert [payment.payment_id for payment in payments] == [
        DEMO_HALL_DEPOSIT_ID,
        DEMO_STUDIO_DEPOSIT_ID,
        DEMO_HALL_BALANCE_ID,
        DEMO_STUDIO_BALANCE_ID,
    ]
    assert [payment.status for payment in payments] == [
        PaymentStatus.PAID,
        PaymentStatus.UNPAID,
        PaymentStatus.UNPAID,
        PaymentStatus.UNPAID,
    ]
    assert (
        sum(payment.amount for payment in payments if payment.status == PaymentStatus.UNPAID)
        == 26_000_000
    )


def test_demo_payment_dates_stay_useful_relative_to_each_seed_run() -> None:
    today = date(2026, 12, 31)

    payments = payment_seeds(today)

    assert [payment.due_date for payment in payments] == [
        today - timedelta(days=45),
        today + timedelta(days=7),
        today + timedelta(days=30),
        today + timedelta(days=90),
    ]


def test_seed_demo_data_is_idempotent(monkeypatch: Any) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.records: dict[tuple[type, UUID], object] = {}
            self.commits = 0

        def add(self, value: object) -> None:
            self.records[(type(value), value.id)] = value  # type: ignore[attr-defined]

        def get(self, model: type, record_id: UUID) -> object | None:
            return self.records.get((model, record_id))

        def scalar(self, _statement: object) -> WeddingPlanMember | None:
            return next(
                (
                    value
                    for (model, _record_id), value in self.records.items()
                    if model is WeddingPlanMember
                ),
                None,
            )  # type: ignore[return-value]

        def flush(self) -> None:
            pass

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            raise AssertionError("seed should not roll back")

    class FakePlanRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        def lock_user_plan(self, _user_id: UUID) -> None:
            pass

        def get_current_for_user(self, _user_id: UUID) -> WeddingPlan | None:
            return next(
                (
                    value
                    for (model, _record_id), value in self.session.records.items()
                    if model is WeddingPlan
                ),
                None,
            )  # type: ignore[return-value]

        def get_initial_asset(self, _plan_id: UUID) -> Asset | None:
            return next(
                (
                    value
                    for (model, _record_id), value in self.session.records.items()
                    if model is Asset
                ),
                None,
            )  # type: ignore[return-value]

    class FakeLoginService:
        def __init__(self, *_args: object) -> None:
            pass

        def login(self) -> None:
            pass

    from app.application import demo_seed

    monkeypatch.setattr(demo_seed, "DemoLoginService", FakeLoginService)
    monkeypatch.setattr(demo_seed, "WeddingPlanRepository", FakePlanRepository)
    session = FakeSession()
    configuration = Settings(
        _env_file=None,
        demo_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        demo_user_login_id="demo",
        demo_user_display_name="Demo",
        demo_user_email=None,
    )

    first = seed_demo_data(session, configuration, today=date(2026, 9, 1))  # type: ignore[arg-type]
    second = seed_demo_data(session, configuration, today=date(2026, 9, 1))  # type: ignore[arg-type]

    assert first == second
    assert session.commits == 2
    assert sum(model is WeddingPlan for model, _record_id in session.records) == 1
    assert sum(model is Asset for model, _record_id in session.records) == 1
    assert sum(model is Document for model, _record_id in session.records) == 2
    assert sum(model is Contract for model, _record_id in session.records) == 2
    assert sum(model is Payment for model, _record_id in session.records) == 4
