from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from app.core.config import settings
from app.domains.documents import service as document_service


def test_resolve_document_scope_prefers_current_user_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = SimpleNamespace(id=UUID("10000000-0000-0000-0000-000000000001"))
    member = SimpleNamespace(id=UUID("10000000-0000-0000-0000-000000000002"))
    repository = Mock()
    repository.get_current_for_user.return_value = plan
    repository.get_member_for_user.return_value = member
    monkeypatch.setattr(document_service, "WeddingPlanRepository", lambda _db: repository)

    scope = document_service._resolve_document_scope(Mock())

    assert scope == (plan.id, member.id)
    repository.get_current_for_user.assert_called_once_with(settings.demo_user_id)
    repository.get_member_for_user.assert_called_once_with(plan.id, settings.demo_user_id)


def test_resolve_document_scope_falls_back_before_plan_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Mock()
    repository.get_current_for_user.return_value = None
    monkeypatch.setattr(document_service, "WeddingPlanRepository", lambda _db: repository)

    scope = document_service._resolve_document_scope(Mock())

    assert scope == (settings.demo_wedding_plan_id, settings.demo_member_id)
    repository.get_member_for_user.assert_not_called()
