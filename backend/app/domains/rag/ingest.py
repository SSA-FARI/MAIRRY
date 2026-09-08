import argparse
from pathlib import Path

from sqlalchemy import delete, select

from ai.rag.chunking import ClauseSource, chunk_clause_sources, split_structured_clauses
from ai.rag.schemas import KnowledgeType
from app.core.config import settings
from app.core.database import SessionLocal
from app.domains.rag.models import DocumentChunk
from app.domains.rag.service import build_embedding_client, close_embedding_http_clients

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "ai" / "knowledge"
SOURCE_FILES = {
    "faq": (KnowledgeType.SERVICE_FAQ, KNOWLEDGE_ROOT / "service-faq.md"),
    "domain": (KnowledgeType.DOMAIN_KNOWLEDGE, KNOWLEDGE_ROOT / "domain-knowledge.md"),
}


def ingest(source: str) -> tuple[int, int]:
    knowledge_type, path = SOURCE_FILES[source]
    text = path.read_text(encoding="utf-8")
    sources = split_structured_clauses(text.replace("## ", "특약사항 "))
    if not sources:
        sources = [ClauseSource(title=path.stem, content=text)]
    chunks = chunk_clause_sources(
        sources,
        knowledge_type=knowledge_type,
        namespace=f"curated:{path.name}",
        chunk_size=settings.rag_chunk_size,
        overlap=settings.rag_chunk_overlap,
    )
    embedder = build_embedding_client(settings)
    session = SessionLocal()
    created = 0
    unchanged = 0
    try:
        incoming_ids = {chunk.chunk_id for chunk in chunks}
        existing_ids = set(
            session.scalars(
                select(DocumentChunk.chunk_id).where(
                    DocumentChunk.knowledge_type == knowledge_type.value
                )
            ).all()
        )
        for chunk in chunks:
            if chunk.chunk_id in existing_ids:
                unchanged += 1
                continue
            vector = embedder.embed(chunk.content)
            session.add(
                DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    content_hash=chunk.content_hash,
                    knowledge_type=knowledge_type.value,
                    title=chunk.title,
                    clause_title=chunk.clause_title,
                    page_number=chunk.page,
                    chunk_index=chunk.chunk_index,
                    document_version=1,
                    content=chunk.content,
                    embedding=vector,
                    embedding_vector=vector,
                    embedding_model=embedder.model_name,
                    embedding_version=embedder.version,
                    embedding_dimensions=embedder.dimensions,
                    active=True,
                )
            )
            created += 1
        stale_ids = existing_ids - incoming_ids
        if stale_ids:
            session.execute(delete(DocumentChunk).where(DocumentChunk.chunk_id.in_(stale_ids)))
        session.commit()
    finally:
        session.close()
        close_embedding_http_clients()
    return created, unchanged


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently ingest curated RAG knowledge")
    parser.add_argument("--source", choices=sorted(SOURCE_FILES), required=True)
    args = parser.parse_args()
    created, unchanged = ingest(args.source)
    print(f"source={args.source} created={created} unchanged={unchanged}")


if __name__ == "__main__":
    main()
