import logging
from types import SimpleNamespace

from ai.rag import ingest_seed
from ai.rag.dataset_schemas import RagDatasetRecord
from ai.rag.ingest_seed import ingest_records


class FakeEmbeddingClient:
    model_name = "text-embedding-3-small"
    version = "v1"
    dimensions = 3

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts) -> list[list[float]]:
        batch = list(texts)
        if not batch:
            return []
        self.calls.append(batch)
        return [[1.0, 0.0, 0.0] for _ in batch]


class FakeScalars:
    def __init__(self, items) -> None:
        self._items = items

    def all(self):
        return self._items


class FakeSession:
    def __init__(self) -> None:
        self.items = []
        self.committed = False
        self.closed = False

    def scalars(self, statement):
        return FakeScalars(self.items)

    def add(self, item) -> None:
        self.items.append(item)

    def execute(self, _statement):
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _record(content: str = "계약서를 업로드합니다.") -> RagDatasetRecord:
    return RagDatasetRecord.model_validate(
        {
            "id": "faq-upload-test",
            "knowledge_type": "SERVICE_FAQ",
            "title": "업로드",
            "content": content,
            "source": "service_faq_test",
            "scope": "GLOBAL",
            "question": "어떻게 업로드하나요?",
        }
    )


def test_unchanged_seed_is_not_embedded_twice() -> None:
    session = FakeSession()
    client = FakeEmbeddingClient()

    first = ingest_records(session, [_record()], client, demo_plan_id=None)
    second = ingest_records(session, [_record()], client, demo_plan_id=None)

    assert first == (1, 0, 0)
    assert second == (0, 1, 0)
    assert len(client.calls) == 1
    assert session.items[0].embedding_model == "text-embedding-3-small"


def test_changed_content_reembeds_only_that_record() -> None:
    session = FakeSession()
    client = FakeEmbeddingClient()
    ingest_records(session, [_record()], client, demo_plan_id=None)

    indexed, skipped, _ = ingest_records(
        session, [_record("PDF 파일을 선택해 업로드합니다.")], client, demo_plan_id=None
    )

    assert (indexed, skipped) == (1, 0)
    assert len(client.calls) == 2


def test_startup_ingestion_logs_vector_and_embedding_summary(monkeypatch, caplog) -> None:
    session = FakeSession()
    client = FakeEmbeddingClient()
    configuration = SimpleNamespace(
        embedding_model_name="text-embedding-3-small",
        demo_wedding_plan_id=None,
    )
    monkeypatch.setattr(ingest_seed, "DATASET_FILES", {"service_faq": object()})
    monkeypatch.setattr(ingest_seed, "load_dataset", lambda _name: [_record()])
    monkeypatch.setattr(ingest_seed, "_embedding_client", lambda *_args: client)
    monkeypatch.setattr(ingest_seed, "SessionLocal", lambda: session)

    with caplog.at_level(logging.INFO, logger="ai.rag.ingest_seed"):
        summary = ingest_seed.ingest_configured_seed(configuration)  # type: ignore[arg-type]

    assert summary["service_faq"] == {
        "loaded": 1,
        "indexed": 1,
        "skipped_unchanged": 0,
        "deleted": 0,
        "disabled": 0,
    }
    assert session.committed is True
    assert session.closed is True
    assert "embeddingModel=text-embedding-3-small" in caplog.text
    assert "vectorsIndexed=1" in caplog.text
    assert "loaded=1 indexed=1 skippedUnchanged=0" in caplog.text
