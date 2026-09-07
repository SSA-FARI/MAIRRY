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

    def scalars(self, statement):
        return FakeScalars(self.items)

    def add(self, item) -> None:
        self.items.append(item)


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
