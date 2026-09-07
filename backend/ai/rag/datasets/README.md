# RAG Seed Dataset

실제 적재 입력은 UTF-8 JSONL인 다음 네 파일이다.

| Dataset | knowledge_type | 최소 개수 | 기본 검색 |
| --- | --- | ---: | --- |
| `contract_clauses.jsonl` | `CONTRACT_CLAUSE` | 15 | Demo Plan 전용 |
| `wedding_domain_terms.jsonl` | `DOMAIN_KNOWLEDGE` | 25 | 활성 |
| `service_faq.jsonl` | `SERVICE_FAQ` | 20 | 활성 |
| `consultation_examples.jsonl` | `CURATED_QA` | 10 | 비활성 |

각 줄은 `RagDatasetRecord`로 검증한다. `id`, `knowledge_type`, `title`, `content`, `source`,
`scope`, `enabled`, `version`이 공통 필드이며 유형별 필드는
`backend/ai/rag/dataset_schemas.py`에 정의되어 있다. Markdown 파일과 기존 하이픈 이름 JSONL은
참고 자료이며 적재 입력이 아니다.

```powershell
cd backend
python -m ai.rag.ingest_seed --dataset all --dry-run
python -m ai.rag.ingest_seed --dataset all
```

실제 적재에는 `.env`의 `AI_API_KEY`가 필요하다. GMS에서 발급받은 키나 실제 개인정보를
Dataset에 넣지 않는다.

서버는 기본적으로 시작할 때 네 JSONL을 검증하고 멱등 적재한다
(`RAG_SEED_INGEST_ON_STARTUP=true`). content hash와 embedding model/version/dimensions가 같은
레코드는 GMS embedding API를 다시 호출하지 않는다. 로그에는 원문이나 벡터 배열 대신 모델명,
차원, dataset별 loaded/indexed/skippedUnchanged/disabled/deleted 개수만 남긴다.
