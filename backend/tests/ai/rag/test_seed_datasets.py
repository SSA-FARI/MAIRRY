import json

import pytest

from ai.rag.dataset_schemas import RagDatasetRecord, build_embedding_text
from ai.rag.ingest_seed import DATASET_FILES, load_dataset
from ai.rag.schemas import KnowledgeType

EXPECTED_COUNTS = {
    "contract_clauses": 15,
    "wedding_domain_terms": 25,
    "service_faq": 20,
    "consultation_examples": 10,
}


@pytest.mark.parametrize("dataset_name", EXPECTED_COUNTS)
def test_seed_dataset_is_valid_utf8_jsonl_with_unique_ids(dataset_name: str) -> None:
    path = DATASET_FILES[dataset_name]
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    assert raw_lines
    assert all(line.strip() and not line.lstrip().startswith(("[", "#")) for line in raw_lines)
    assert all(isinstance(json.loads(line), dict) for line in raw_lines)

    records = load_dataset(dataset_name)
    assert len(records) >= EXPECTED_COUNTS[dataset_name]
    assert len({record.id for record in records}) == len(records)
    assert all(record.content.strip() for record in records)


def test_consultation_examples_are_disabled_by_default() -> None:
    assert all(not record.enabled for record in load_dataset("consultation_examples"))


def test_embedding_text_includes_aliases_but_not_full_metadata() -> None:
    record = RagDatasetRecord.model_validate(
        {
            "id": "term-test",
            "knowledge_type": "DOMAIN_KNOWLEDGE",
            "title": "보증인원",
            "content": "최소 준비 인원입니다.",
            "source": "test",
            "scope": "GLOBAL",
            "term": "보증인원",
            "aliases": ["최소 보증인원"],
            "priority": 99,
        }
    )

    text = build_embedding_text(record)
    assert "최소 보증인원" in text
    assert "priority" not in text


def test_dataset_knowledge_types_match_their_source() -> None:
    expected = {
        "contract_clauses": KnowledgeType.CONTRACT_CLAUSE,
        "wedding_domain_terms": KnowledgeType.DOMAIN_KNOWLEDGE,
        "service_faq": KnowledgeType.SERVICE_FAQ,
        "consultation_examples": KnowledgeType.CURATED_QA,
    }
    for name, knowledge_type in expected.items():
        assert {record.knowledge_type for record in load_dataset(name)} == {knowledge_type}
