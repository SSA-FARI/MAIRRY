from __future__ import annotations

import argparse
import hashlib
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai.rag.dataset_schemas import KnowledgeScope, RagDatasetRecord, build_embedding_text
from ai.rag.embeddings import EmbeddingClient, OpenAiEmbeddingClient
from app.core.config import Settings, settings
from app.core.database import SessionLocal
from app.domains.rag.models import DocumentChunk
from app.domains.wedding_plan.models import WeddingPlan

DATASET_ROOT = Path(__file__).resolve().parent / "datasets"
DATASET_FILES = {
    "contract_clauses": DATASET_ROOT / "contract_clauses.jsonl",
    "wedding_domain_terms": DATASET_ROOT / "wedding_domain_terms.jsonl",
    "service_faq": DATASET_ROOT / "service_faq.jsonl",
    "consultation_examples": DATASET_ROOT / "consultation_examples.jsonl",
}


def load_dataset(name: str) -> list[RagDatasetRecord]:
    path = DATASET_FILES[name]
    records: list[RagDatasetRecord] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            raise ValueError(f"{path.name}:{line_number}: blank lines are not allowed")
        try:
            record = RagDatasetRecord.model_validate_json(raw_line)
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"{path.name}:{line_number}: invalid record: {exc}") from exc
        if record.id in seen_ids:
            raise ValueError(f"{path.name}:{line_number}: duplicate id: {record.id}")
        seen_ids.add(record.id)
        records.append(record)
    return records


def _content_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _vector_id(record: RagDatasetRecord) -> str:
    return f"rag-seed:{record.knowledge_type.value}:{record.id}:v{record.version}"


def _metadata(record: RagDatasetRecord) -> dict[str, object]:
    return record.model_dump(mode="json", exclude={"content"})


def ingest_records(
    session: Session,
    records: Iterable[RagDatasetRecord],
    embedding_client: EmbeddingClient,
    *,
    demo_plan_id,
    sync: bool = False,
) -> tuple[int, int, int]:
    record_list = list(records)
    if any(record.scope == KnowledgeScope.DEMO_PLAN for record in record_list) and (
        demo_plan_id is None or session.get(WeddingPlan, demo_plan_id) is None
    ):
        raise RuntimeError("Demo WeddingPlan is required before contract seed ingestion")

    existing = {
        item.chunk_id: item
        for item in session.scalars(
            select(DocumentChunk).where(
                DocumentChunk.source.in_({record.source for record in record_list})
            )
        ).all()
    }
    existing_by_record = {
        item.dataset_record_id: item for item in existing.values() if item.dataset_record_id
    }
    changed: list[tuple[RagDatasetRecord, str, str]] = []
    skipped = 0
    for record in record_list:
        text = build_embedding_text(record)
        digest = _content_hash(text)
        current = existing.get(_vector_id(record)) or existing_by_record.get(record.id)
        if (
            current is not None
            and current.chunk_id == _vector_id(record)
            and current.content_hash == digest
            and current.embedding_model == embedding_client.model_name
            and current.embedding_version == embedding_client.version
            and current.embedding_dimensions == embedding_client.dimensions
        ):
            current.active = record.enabled
            current.chunk_metadata = _metadata(record)
            skipped += 1
        else:
            changed.append((record, text, digest))

    vectors = embedding_client.embed_many(text for _, text, _ in changed)
    for (record, text, digest), vector in zip(changed, vectors, strict=True):
        vector_id = _vector_id(record)
        current = existing.get(vector_id) or existing_by_record.get(record.id)
        if current is None:
            current = DocumentChunk(chunk_id=vector_id)
            session.add(current)
        else:
            current.chunk_id = vector_id
        current.content_hash = digest
        current.knowledge_type = record.knowledge_type.value
        current.wedding_plan_id = demo_plan_id if record.scope == KnowledgeScope.DEMO_PLAN else None
        current.document_id = None
        current.contract_id = None
        current.title = record.title
        current.clause_title = record.clause_type
        current.page_number = record.page
        current.chunk_index = 0
        current.document_version = record.version
        current.content = text
        current.embedding = vector
        current.embedding_model = embedding_client.model_name
        current.embedding_version = embedding_client.version
        current.embedding_dimensions = embedding_client.dimensions
        current.source = record.source
        current.dataset_record_id = record.id
        current.chunk_metadata = _metadata(record)
        current.active = record.enabled

    deleted = 0
    if sync and record_list:
        incoming = {_vector_id(record) for record in record_list}
        stale = [item.id for item in existing.values() if item.chunk_id not in incoming]
        if stale:
            result = session.execute(delete(DocumentChunk).where(DocumentChunk.id.in_(stale)))
            deleted = result.rowcount or 0
    return len(changed), skipped, deleted


def _embedding_client(configuration: Settings, model_name: str) -> OpenAiEmbeddingClient:
    return OpenAiEmbeddingClient(
        api_key=configuration.ai_api_key,
        base_url=configuration.ai_base_url,
        model_name=model_name,
        version=configuration.embedding_version,
        dimensions=configuration.embedding_dimensions,
        timeout_seconds=configuration.ai_timeout_seconds,
        batch_size=configuration.embedding_batch_size,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and idempotently ingest RAG seed data")
    parser.add_argument("--dataset", choices=["all", *DATASET_FILES], default="all")
    parser.add_argument("--embedding-model", default=settings.embedding_model_name)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    names = list(DATASET_FILES) if args.dataset == "all" else [args.dataset]
    loaded = {name: load_dataset(name) for name in names}
    if args.dry_run:
        print(f"RAG seed validation completed: {sum(map(len, loaded.values()))} records")
        return

    client = _embedding_client(settings, args.embedding_model)
    session = SessionLocal()
    try:
        for name, records in loaded.items():
            indexed, skipped, deleted = ingest_records(
                session,
                records,
                client,
                demo_plan_id=settings.demo_wedding_plan_id,
                sync=args.sync,
            )
            print(f"{name}: indexed={indexed} skipped_unchanged={skipped} deleted={deleted}")
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print(f"RAG seed ingestion completed - Embedding model: {client.model_name}")


if __name__ == "__main__":
    main()
