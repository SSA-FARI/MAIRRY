from ai.providers.base import ChatProvider
from ai.providers.openai_provider import OpenAiProvider
from app.core.config import Settings


def build_chat_provider(configuration: Settings) -> ChatProvider | None:
    """Build the live Chat provider only when all required settings are present."""
    if not configuration.ai_api_key.strip() or not configuration.ai_model.strip():
        return None
    return OpenAiProvider(
        api_key=configuration.ai_api_key,
        model=configuration.ai_model,
        base_url=configuration.ai_base_url,
        timeout_seconds=configuration.ai_timeout_seconds,
    )
