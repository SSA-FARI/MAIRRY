from types import SimpleNamespace

from ai.providers.openai_provider import OpenAiProvider
from app.application.chat_provider import build_chat_provider


def test_build_chat_provider_uses_configured_model_and_timeout() -> None:
    provider = build_chat_provider(
        SimpleNamespace(
            ai_api_key="test-key",
            ai_model="test-model",
            ai_base_url="https://gateway.example/v1",
            ai_timeout_seconds=17,
        )
    )

    assert isinstance(provider, OpenAiProvider)
    assert provider._model == "test-model"
    assert provider._timeout_seconds == 17
    assert provider._responses_url == "https://gateway.example/v1/responses"


def test_build_chat_provider_returns_none_for_incomplete_configuration() -> None:
    assert (
        build_chat_provider(
            SimpleNamespace(
                ai_api_key="",
                ai_model="test-model",
                ai_base_url="https://api.openai.com/v1",
                ai_timeout_seconds=17,
            )
        )
        is None
    )
    assert (
        build_chat_provider(
            SimpleNamespace(
                ai_api_key="test-key",
                ai_model="  ",
                ai_base_url="https://api.openai.com/v1",
                ai_timeout_seconds=17,
            )
        )
        is None
    )
