from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _set_demo_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_USER_ID", "00000000-0000-0000-0000-000000000123")
    monkeypatch.setenv("DEMO_USER_LOGIN_ID", "demo")
    monkeypatch.setenv("DEMO_USER_DISPLAY_NAME", "Demo User")
    monkeypatch.setenv("DEMO_USER_EMAIL", "")


def test_settings_reads_demo_user_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_demo_environment(monkeypatch)

    configuration = Settings(_env_file=None)

    assert configuration.demo_user_id == UUID("00000000-0000-0000-0000-000000000123")
    assert configuration.demo_user_login_id == "demo"
    assert configuration.demo_user_display_name == "Demo User"
    assert configuration.demo_user_email is None


def test_settings_rejects_invalid_demo_user_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_demo_environment(monkeypatch)
    monkeypatch.setenv("DEMO_USER_ID", "not-a-uuid")

    with pytest.raises(ValidationError, match="demo_user_id"):
        Settings(_env_file=None)


def test_settings_requires_demo_profile_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable_name in (
        "DEMO_USER_ID",
        "DEMO_USER_LOGIN_ID",
        "DEMO_USER_DISPLAY_NAME",
        "DEMO_USER_EMAIL",
    ):
        monkeypatch.delenv(variable_name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
