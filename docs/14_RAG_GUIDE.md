# LangGraph RAG 운영 가이드

## 흐름

Chat은 `prepare → classify → tool/retrieve → generate` LangGraph StateGraph를 사용한다. 금액과
일정은 기존 Backend Tool만 사용하며 계약 조항, 서비스 도움말과 용어 설명만 RAG에서 찾는다.
혼합 질문은 Tool 실행 후 RAG 검색을 이어서 수행한다.

계약 조항 검색은 SQL 단계에서 현재 Demo User가 멤버인 활성 WeddingPlan, CONFIRMED 계약,
active 청크를 제한한다. 요청의 ID나 질문 속 ID를 접근 범위로 사용하지 않는다. 공용 FAQ와
도메인 문서만 wedding_plan_id가 null이다.

## 저장과 색인

현재 PostgreSQL 이미지에 pgvector가 없으므로 별도 vector 서버를 추가하지 않는다. embedding은
JSONB로 영속화하고, metadata로 후보를 제한한 다음 application layer에서 cosine similarity를
계산한다. 문서 적재와 검색 질문은 모두 SSAFY GMS의 `text-embedding-3-small`을 사용한다. 기본
벡터 차원은 1536이며 각 청크에 `embedding_model`, `embedding_version`, `embedding_dimensions`를
저장하고 동일한 profile만 검색해 다른 모델의 벡터가 섞이지 않게 한다.

```dotenv
AI_API_KEY=...
AI_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_VERSION=v1
EMBEDDING_DIMENSIONS=1536
```

계약 확정·수정 트랜잭션은 `rag_index_jobs`에 PENDING 작업을 멱등 등록한다. API 응답 후 background
task가 INDEXING → INDEXED/FAILED 상태를 기록한다. 새 버전 저장이 완료될 때 이전 청크를 inactive로
전환하므로 두 버전이 동시에 검색되지 않는다. 계약 삭제는 청크를 즉시 삭제하고 Contract 상태를
함께 조회하는 검색 조건으로 잔존 노출도 방지한다.

FAILED/PENDING 작업은 최대 3회까지 다음 명령으로 재처리할 수 있다.

```powershell
python -m app.domains.rag.worker
python -m app.domains.rag.worker --contract-id <UUID>
```

## Seed Dataset 적재

Dataset은 `backend/ai/rag/datasets/`의 UTF-8 JSONL 4종이다. Migration 적용 및 Demo seed 생성
후 다음 명령으로 schema만 검증하거나 실제 embedding을 적재한다.

```powershell
cd backend
python -m ai.rag.ingest_seed --dataset all --dry-run
python -m ai.rag.ingest_seed --dataset all
python -m ai.rag.ingest_seed --dataset service_faq --sync
$env:RUN_RAG_INTEGRATION="1"
python -m pytest tests/ai/rag -m integration
```

vector ID는 `rag-seed:{knowledge_type}:{record_id}:v{version}` 형식이다. 정규화된 embedding text의
SHA-256 content hash가 같으면 API를 다시 호출하지 않고, 변경된 레코드만 재임베딩한다. `--sync`는
선택한 Dataset source의 사라진 Seed만 삭제하며 사용자 계약 청크나 다른 Dataset은 건드리지 않는다.
`consultation_examples`는 저장할 수 있지만 기본 `enabled=false`라 검색에서 제외한다.

기존 `legacy-hashing-384` 벡터는 검색 profile에서 제외된다. 모델이나 차원을 바꾼 경우 서버 시작 시
전체 삭제하지 말고 위 적재 명령과 계약 색인 worker를 명시적으로 다시 실행한다.
