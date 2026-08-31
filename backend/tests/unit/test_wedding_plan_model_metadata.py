from sqlalchemy import CheckConstraint, Enum, UniqueConstraint

from app.domains.wedding_plan.models import Asset, WeddingPlan, WeddingPlanMember


def test_wedding_plan_model_matches_erd() -> None:
    table = WeddingPlan.__table__

    assert list(table.columns.keys()) == [
        "id",
        "wedding_date",
        "status",
        "created_at",
        "updated_at",
    ]
    assert table.c.wedding_date.nullable is True
    assert table.c.status.nullable is False
    assert isinstance(table.c.status.type, Enum)
    assert table.c.status.type.enums == ["ACTIVE", "COMPLETED"]


def test_wedding_plan_member_model_matches_erd() -> None:
    table = WeddingPlanMember.__table__

    assert list(table.columns.keys()) == [
        "id",
        "wedding_plan_id",
        "user_id",
        "role",
        "joined_at",
    ]
    assert {foreign_key.target_fullname for foreign_key in table.foreign_keys} == {
        "users.id",
        "wedding_plans.id",
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_columns == {("wedding_plan_id", "user_id")}


def test_asset_model_matches_erd() -> None:
    table = Asset.__table__

    assert list(table.columns.keys()) == [
        "id",
        "wedding_plan_id",
        "owner_member_id",
        "owner_type",
        "category",
        "amount",
        "label",
        "created_at",
        "updated_at",
    ]
    assert {foreign_key.target_fullname for foreign_key in table.foreign_keys} == {
        "wedding_plans.id",
        "wedding_plan_members.id",
    }
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_names == {"ck_assets_amount_non_negative", "ck_assets_owner_member"}
    assert {index.name for index in table.indexes} == {"ix_assets_wedding_plan_id"}
