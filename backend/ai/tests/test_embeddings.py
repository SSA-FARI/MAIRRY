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


def test_owned_http_client_is_reused_and_closed_once(monkeypatch) -> None:
    created: list[object] = []

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.is_closed = False
            self.posts = 0
            self.close_calls = 0
            created.append(self)

        def post(self, url, **_kwargs) -> httpx.Response:
            self.posts += 1
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "model": "text-embedding-3-small",
                    "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}],
                },
            )

        def close(self) -> None:
            self.close_calls += 1
            self.is_closed = True

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OpenAiEmbeddingClient(
        api_key="test-gms-key",
        base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
        dimensions=3,
        batch_size=1,
    )

    client.embed_many(["하나", "둘"])
    client.close()
    client.close()

    assert len(created) == 1
    assert created[0].posts == 2
    assert created[0].close_calls == 1


def test_injected_http_client_is_not_closed_by_embedding_adapter() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}],
            },
        )
    )
    injected = httpx.Client(transport=transport)
    client = OpenAiEmbeddingClient(
        api_key="test-gms-key",
        base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
        dimensions=3,
        http_client=injected,
    )

    client.embed("질문")
    client.close()

    assert injected.is_closed is False
    injected.close()


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
