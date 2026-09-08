from types import SimpleNamespace

from app.domains.rag import service


def test_embedding_http_client_is_shared_and_closed_once(monkeypatch) -> None:
    created: list[object] = []

    class FakeHttpClient:
        def __init__(self, **_kwargs) -> None:
            self.is_closed = False
            self.close_calls = 0
            created.append(self)

        def close(self) -> None:
            self.is_closed = True
            self.close_calls += 1

    service.close_embedding_http_clients()
    monkeypatch.setattr(service.httpx, "Client", FakeHttpClient)
    configuration = SimpleNamespace(
        ai_api_key="test-key",
        ai_base_url="https://example.test/v1",
        embedding_model_name="text-embedding-3-small",
        embedding_version="v1",
        embedding_dimensions=1536,
        ai_timeout_seconds=45,
        embedding_batch_size=64,
    )

    first = service.build_embedding_client(configuration)  # type: ignore[arg-type]
    second = service.build_embedding_client(configuration)  # type: ignore[arg-type]
    service.close_embedding_http_clients()
    service.close_embedding_http_clients()

    assert first._http_client is second._http_client
    assert len(created) == 1
    assert created[0].close_calls == 1
