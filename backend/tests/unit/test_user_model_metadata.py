"""Metadata-level tests for the users table mapping."""

from sqlalchemy import DateTime, String

from app.domains.users.models import User


def test_user_model_matches_erd_columns_and_constraints() -> None:
    table = User.__table__

    assert table.name == "users"
    assert list(table.columns.keys()) == [
        "id",
        "login_id",
        "password_hash",
        "display_name",
        "email",
        "created_at",
        "updated_at",
    ]

    assert table.c.id.primary_key is True
    assert table.c.id.nullable is False

    assert isinstance(table.c.login_id.type, String)
    assert table.c.login_id.type.length == 50
    assert table.c.login_id.nullable is False
    assert table.c.login_id.unique is True

    assert isinstance(table.c.password_hash.type, String)
    assert table.c.password_hash.type.length == 255
    assert table.c.password_hash.nullable is False
    assert "bcrypt hash only" in table.c.password_hash.comment

    assert isinstance(table.c.display_name.type, String)
    assert table.c.display_name.type.length == 50
    assert table.c.display_name.nullable is False

    assert isinstance(table.c.email.type, String)
    assert table.c.email.type.length == 255
    assert table.c.email.nullable is True
    assert table.c.email.unique is True

    for column_name in ("created_at", "updated_at"):
        column = table.c[column_name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is False
        assert str(column.server_default.arg) == "now()"

    assert table.c.updated_at.onupdate is not None
    assert not table.indexes


def test_user_password_hash_is_not_part_of_any_public_response_schema() -> None:
    from app.main import app

    schemas = app.openapi().get("components", {}).get("schemas", {})

    for schema in schemas.values():
        properties = schema.get("properties", {})
        assert "password_hash" not in properties
        assert "passwordHash" not in properties
