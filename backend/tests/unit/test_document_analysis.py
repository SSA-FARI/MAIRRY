from ai.providers.openai_provider import OpenAiProvider
from app.application.document_analysis import _build_document_extraction_provider
from app.core.config import settings


def test_provider_is_disabled_when_credentials_are_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "")
    monkeypatch.setattr(settings, "ai_model", "test-model")

    assert _build_document_extraction_provider() is None


def test_provider_uses_runtime_ai_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-api-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_base_url", "https://gms.example/v1/")
    monkeypatch.setattr(settings, "ai_timeout_seconds", 17)

    provider = _build_document_extraction_provider()

    assert isinstance(provider, OpenAiProvider)
    assert provider._model == "test-model"
    assert provider._timeout_seconds == 17
    assert provider._responses_url == "https://gms.example/v1/responses"
