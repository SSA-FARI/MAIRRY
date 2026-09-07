import httpx
import pytest

from ai.rag.embeddings import EmbeddingError, OpenAiEmbeddingClient, cosine_similarity


def _client(handler, *, dimensions: int = 3, batch_size: int = 64) -> OpenAiEmbeddingClient:
    return OpenAiEmbeddingClient(
        api_key="test-gms-key",
        base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1/",
        dimensions=dimensions,
        batch_size=batch_size,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_embedding_client_uses_gms_endpoint_model_and_batch_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://gms.ssafy.io/gmsapi/api.openai.com/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer test-gms-key"
        assert b'"model":"text-embedding-3-small"' in request.content
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                ],
            },
        )

    assert _client(handler).embed_many(["문서", "질문"]) == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]


def test_embedding_client_batches_requests() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}],
            },
        )

    _client(handler, batch_size=1).embed_many(["하나", "둘"])
    assert calls == 2


def test_embedding_client_accepts_full_embeddings_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/v1/embeddings")
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}],
            },
        )

    client = OpenAiEmbeddingClient(
        api_key="test-gms-key",
        base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1/embeddings",
        dimensions=3,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.embed("질문") == [1.0, 0.0, 0.0]


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (httpx.ReadTimeout("late"), "timed out"),
        (httpx.ConnectError("down"), "unavailable"),
    ],
)
def test_embedding_client_maps_transport_failures(exception: Exception, message: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    with pytest.raises(EmbeddingError, match=message):
        _client(handler).embed("질문")


def test_embedding_client_rejects_wrong_model_or_dimension() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"model": "other-model", "data": [{"index": 0, "embedding": [1.0]}]},
        )

    with pytest.raises(EmbeddingError, match="different model"):
        _client(handler).embed("질문")


def test_cosine_similarity_normalizes_provider_vectors() -> None:
    assert cosine_similarity([2.0, 0.0], [4.0, 0.0]) == 1.0
