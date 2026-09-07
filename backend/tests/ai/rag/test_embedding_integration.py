import os

import pytest

from app.core.config import settings
from app.domains.rag.service import build_embedding_client


@pytest.mark.integration
def test_configured_embedding_provider_returns_expected_model_and_dimension() -> None:
    if os.getenv("RUN_RAG_INTEGRATION") != "1" or not settings.ai_api_key:
        pytest.skip("Set RUN_RAG_INTEGRATION=1 and AI_API_KEY to run this live test")

    client = build_embedding_client(settings)
    vector = client.embed("보증인원이 뭐야?")

    assert client.model_name == "text-embedding-3-small"
    assert len(vector) == settings.embedding_dimensions == 1536
