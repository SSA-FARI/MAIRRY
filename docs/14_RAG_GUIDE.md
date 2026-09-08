# LangGraph RAG 운영 가이드

## 흐름

Chat은 `prepare → classify → tool/retrieve → generate` LangGraph StateGraph를 사용한다. 금액과
일정은 기존 Backend Tool만 사용하며 계약 조항, 서비스 도움말과 용어 설명만 RAG에서 찾는다.
혼합 질문은 Tool 실행 후 RAG 검색을 이어서 수행한다.

계약 조항 검색은 SQL 단계에서 현재 Demo User가 멤버인 활성 WeddingPlan, CONFIRMED 계약,
active 청크를 제한한다. 요청의 ID나 질문 속 ID를 접근 범위로 사용하지 않는다. 공용 FAQ와
도메인 문서만 wedding_plan_id가 null이다.

## 저장과 색인

Compose의 PostgreSQL 16은 pgvector 확장 포함 이미지로 실행한다. 기존 JSONB embedding은 안전한
rollback과 데이터 보존을 위해 유지하고, 검색에는 1536차원 `embedding_vector`를 사용한다. metadata
범위 조건, cosine distance 정렬, score threshold와 top-k는 모두 SQL에서 적용한다. 문서 적재와 검색
질문은 모두 SSAFY GMS의 `text-embedding-3-small`을 사용한다. 기본
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
task가 즉시 처리를 시도하고, lifespan reconciliation loop가 PENDING/FAILED 및 lease가 만료된
INDEXING 작업을 계속 복구한다. claim은 짧은 `FOR UPDATE SKIP LOCKED` transaction에서 attempts와
`locked_at`을 저장한 뒤 commit하므로 embedding 동안 row lock을 잡지 않는다. 실패는 독립 Session에서
안전한 error code와 exponential backoff 시각을 기록한다. 새 버전 저장이 완료될 때 이전 청크를
inactive로 전환하므로 두 버전이 동시에 검색되지 않는다. 계약 삭제는 청크를 즉시 삭제하고 Contract
상태를 함께 조회하는 검색 조건으로 잔존 노출도 방지한다.

자동 복구 외에 운영자는 다음 명령으로 한 batch를 즉시 처리할 수 있다.

```powershell
python -m app.domains.rag.worker
python -m app.domains.rag.worker --limit 100
python -m app.domains.rag.worker --contract-id <UUID>
```

## Seed Dataset 적재

Dataset은 `backend/ai/rag/datasets/`의 UTF-8 JSONL 4종이다. Migration 적용 및 Demo seed 생성
후 서버가 시작될 때 자동으로 schema를 검증하고 변경된 레코드만 embedding하여 적재한다.
`RAG_SEED_INGEST_ON_STARTUP=false`로 끌 수 있으며, 다음 명령으로 수동 검증·적재도 가능하다.

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

시작 로그는 embedding model/version/dimensions와 dataset별
`loaded`, `indexed`, `skippedUnchanged`, `disabled`, `deleted` 및 총 vector 개수를 구조화 필드로
남긴다. 질문/청크 원문, API key, embedding vector 자체는 로그에 남기지 않는다. 다중 worker의
동시 시작은 PostgreSQL advisory transaction lock으로 직렬화한다.

기존 `legacy-hashing-384` 벡터는 검색 profile에서 제외된다. 모델이나 차원을 바꾼 경우 서버 시작 시
전체 삭제하지 말고 위 적재 명령과 계약 색인 worker를 명시적으로 다시 실행한다.

좋아. 지금 문서는 내용 자체는 굉장히 잘 정리되어 있는데, **구현 세부사항이 너무 많아서 전체 구조가 한눈에 안 들어오는 상태**야.
그래서 **“전체 흐름 → 핵심 구성 → 상세 흐름 → 문제점 → 우선순위”** 순서로 다시 정리하면 훨씬 보기 좋아져.

아래처럼 정리하는 걸 추천해. 

# MAIRRY AI Chat · RAG 전체 동작 흐름

## 1. 한눈에 보는 전체 구조

MAIRRY는 크게 아래 4가지 영역으로 구성된다.

```text
사용자
  │
  ├─ 계약서 업로드
  │      ↓
  │   AI 문서 분석
  │      ↓
  │   사용자 검토·확정
  │      ↓
  │   계약 정보 DB 저장
  │      ↓
  │   RAG 청크 생성 + 임베딩
  │
  └─ AI 챗봇 질문
         ↓
      질문 분석
         ↓
   ┌───────────────┐
   │               │
 DB Tool          RAG
   │               │
   └──────┬────────┘
          ↓
      LLM 답변 생성
          ↓
       사용자 응답
```

핵심은 다음과 같다.

* **계약 금액 / 납부일 / 자산 / 예상 잔액** → DB Tool
* **해지 / 환불 / 위약금 / 계약 조건** → RAG
* 둘 다 필요한 질문 → **Tool + RAG 혼합**
* 대화 내용은 PostgreSQL에 저장
* RAG 벡터도 별도 Vector DB가 아니라 PostgreSQL에 저장

---

# 2. 핵심 기술 구조

| 영역            | 현재 구현                        |
| ------------- | ---------------------------- |
| Backend       | FastAPI                      |
| DB            | PostgreSQL                   |
| 파일 저장         | MinIO                        |
| AI 문서 분석      | OpenAI-compatible API        |
| Embedding     | `text-embedding-3-small`     |
| RAG 저장        | PostgreSQL `document_chunks` |
| Vector 검색     | PostgreSQL pgvector cosine distance |
| Chat Workflow | LangGraph                    |
| 대화 저장         | PostgreSQL                   |
| Background 처리 | `BackgroundTasks` + lifespan reconciliation |

### 중요한 특징

현재는 별도 Pinecone/Chroma 서버 대신 PostgreSQL pgvector를 사용한다.

```text
PostgreSQL
    ↓
document_chunks
    ├─ content
    ├─ embedding(JSONB, 보존·rollback용)
    ├─ embedding_vector(vector(1536), 검색용)
    ├─ contract_id
    ├─ wedding_plan_id
    └─ metadata
```

형태로 저장한다.

검색할 때는

```text
SQL로 metadata 후보 필터링
→ pgvector cosine distance 정렬
→ SQL score threshold + Top-K
```

방식이다.

---

# 3. 서버 시작 흐름

서버 시작 시 가장 먼저 RAG Seed 데이터를 준비한다.

```text
Docker / FastAPI 실행
        ↓
Settings 로딩
        ↓
FastAPI Router 등록
        ↓
lifespan 실행
        ↓
RAG Seed 자동 적재 여부 확인
        ↓
JSONL Seed 데이터 읽기
        ↓
Embedding 생성
        ↓
document_chunks 저장
        ↓
API 서버 시작
```

조건:

```text
RAG_ENABLED=true

RAG_SEED_INGEST_ON_STARTUP=true
```

일 때 Seed 적재가 수행된다.

---

## Seed 데이터 종류

현재 자동으로 읽는 데이터는 다음 4종류다.

| 데이터                           | 용도          |
| ----------------------------- | ----------- |
| `contract_clauses.jsonl`      | 계약 관련 일반 조항 |
| `wedding_domain_terms.jsonl`  | 웨딩 용어       |
| `service-faq.jsonl`           | 서비스 FAQ     |
| `consultation_examples.jsonl` | 상담 예시       |

예:

```text
사용자:
계약금이 뭐야?

→ DOMAIN_KNOWLEDGE 검색
```

또는

```text
사용자:
계약 취소 시 일반적으로 어떻게 돼?

→ CONTRACT_CLAUSE 검색
```

---

# 4. 계약서 업로드 흐름

사용자가 계약서를 업로드하면 다음 과정을 거친다.

```text
사용자 파일 업로드
       ↓
POST /api/documents
       ↓
파일 형식 검증
       ↓
PDF / JPG / PNG 확인
       ↓
MinIO 원본 저장
       ↓
documents 테이블 저장
       ↓
상태 = UPLOADED
```

지원 형식:

```text
.pdf
.jpg
.jpeg
.png
```

파일 원본은 DB가 아니라

```text
MinIO
```

에 저장한다.

DB에는

```text
파일명
storage key
상태
메타데이터
```

정도만 저장한다.

---

# 5. AI 계약서 분석

업로드 직후 프론트에서 분석 API를 호출한다.

```text
POST /api/documents/{documentId}/analyze
```

상태 흐름:

```text
UPLOADED
   ↓
PROCESSING
   ↓
REVIEW_REQUIRED
```

실패하면

```text
PROCESSING
   ↓
FAILED
```

이 된다.

---

## AI가 추출하는 정보

AI는 계약서에서 다음 정보를 추출한다.

```text
업체명

총 계약 금액

납부 항목
 ├─ 계약금
 ├─ 중도금
 └─ 잔금

납부일

취소 조건

환불 조건

위약금 관련 조항

근거 문장
```

예:

```text
업체명
라온벨 웨딩컨벤션

총액
30,000,000원

계약금
5,000,000원

잔금
25,000,000원

취소 조건
예식 90일 전 취소 시 계약금 환불 불가
```

---

# 6. 사용자 검토 및 계약 확정

AI가 분석한 결과를 바로 계약으로 사용하지 않는다.

사용자가 먼저 확인한다.

```text
AI 분석
   ↓
REVIEW_REQUIRED
   ↓
사용자 검토
   ↓
수정
   ↓
확정
```

확정 API:

```text
PUT /api/documents/{documentId}/confirm
```

확정되면 한 번에 다음 데이터가 저장된다.

```text
contracts

payments

cancellation_terms

documents 상태 변경

rag_index_jobs 생성
```

즉,

```text
문서
→ 계약
→ 지급 일정
→ 취소 조건
```

으로 구조화된다.

---

# 7. 계약서 RAG 생성

계약이 확정되면 RAG 데이터도 생성한다.

```text
계약 확정
    ↓
rag_index_jobs
    ↓
계약 내용 Chunk 생성
    ↓
Embedding 생성
    ↓
document_chunks 저장
```

---

## Chunk에 들어가는 데이터

### 취소 조건

```text
취소 조항 제목
+
요약
+
원문 근거
```

예:

```text
[계약 해지]

예식 90일 전 계약 해지 시
계약금 반환이 불가능합니다.
```

---

### 납부 조건

```text
계약금 지급 조건

중도금 지급 조건

잔금 지급 조건
```

---

### PDF 원문

PDF에서는 텍스트를 추출한 뒤

```text
약 900자
```

단위로 나눈다.

기본 설정:

```text
chunk_size = 900

overlap = 120
```

---

# 8. Embedding 저장 구조

Embedding 정보는 `document_chunks`에 저장된다.

대표 필드:

```text
knowledge_type

wedding_plan_id

document_id

contract_id

content

embedding

embedding_model

embedding_dimensions

page_number

active
```

Embedding 기본 모델:

```text
text-embedding-3-small
```

Embedding 차원:

```text
1536
```

---

# 9. AI 챗봇 요청 흐름

사용자가 질문하면 다음 흐름으로 처리된다.

```text
POST /api/chat
      ↓
대화 조회
      ↓
이전 대화 Context 복원
      ↓
질문 Rewrite
      ↓
질문 유형 판단
      ↓
Tool / RAG / Mixed
      ↓
데이터 조회
      ↓
LLM 답변 생성
      ↓
Citation 생성
      ↓
대화 DB 저장
```

---

# 10. 질문 Rewrite

이전 대화를 활용해 사용자의 질문을 독립적인 질문으로 바꾼다.

예:

```text
사용자
라온벨 계약 해지 수수료 알려줘

AI
라온벨 계약의 해지 조건은 ...

사용자
그럼 예약금은?
```

그대로 검색하면

```text
그럼 예약금은?
```

만 남는다.

따라서 내부적으로

```text
라온벨 웨딩컨벤션 계약의
예약금 또는 계약금은 얼마인가?
```

처럼 변환한다.

---

# 11. Tool / RAG 라우팅

질문의 종류에 따라 데이터 조회 방식이 달라진다.

| 질문            | 처리    |
| ------------- | ----- |
| 계약 총액         | Tool  |
| 계약금           | Tool  |
| 납부 상태         | Tool  |
| 향후 지급일        | Tool  |
| 자산            | Tool  |
| 예상 잔액         | Tool  |
| 해지 조건         | RAG   |
| 환불 조건         | RAG   |
| 위약금           | RAG   |
| 계약 조항         | RAG   |
| 웨딩 용어         | RAG   |
| 서비스 FAQ       | RAG   |
| 계약 조건 + 재무 계산 | Mixed |

---

## 예시 1 — Tool

```text
사용자
라온벨 계약금 얼마야?
```

흐름:

```text
질문 분석
↓
CONTRACT_PAYMENT
↓
getContractDeposit
↓
payments 조회
↓
5,000,000원
```

---

## 예시 2 — RAG

```text
사용자
라온벨 계약 해지하면 위약금이 어떻게 돼?
```

흐름:

```text
질문 분석
↓
RAG
↓
라온벨 contract_id 확인
↓
document_chunks 검색
↓
해지 관련 Chunk 검색
↓
LLM 답변
```

---

## 예시 3 — Mixed

```text
사용자
계약금 환불되면 내 예상 잔액 얼마야?
```

필요 데이터:

```text
환불 가능 여부 → RAG

계약금 → Tool

현재 자산 → Tool

예상 잔액 → Finance 계산
```

따라서

```text
Tool + RAG
```

를 함께 사용한다.

---

# 12. RAG 검색 흐름

RAG 검색은 다음 순서다.

```text
사용자 질문
     ↓
Query Expansion
     ↓
Embedding 생성
     ↓
SQL Scope Filtering
     ↓
후보 Chunk 조회
     ↓
Cosine Similarity
     ↓
Top-K
     ↓
관련성 Filter
     ↓
최종 Context
     ↓
LLM
```

---

# 13. 사용자 계약 데이터 격리

MAIRRY에서 가장 중요한 부분 중 하나다.

다른 사용자의 계약서가 검색되면 안 된다.

검색 전에 SQL 단계에서

```text
wedding_plan_id
```

를 제한한다.

계약이 특정된 경우:

```text
contract_id
```

까지 제한한다.

즉:

```text
사용자 질문
    ↓
현재 WeddingPlan
    ↓
현재 사용자 계약만 후보
    ↓
Vector 검색
```

이다.

Vector 유사도가 높더라도

```text
다른 WeddingPlan 계약
```

은 검색 후보에 포함되지 않는다.

---

# 14. 대화 Context 저장

대화 내용은 PostgreSQL에 저장한다.

```text
chat_conversations

chat_messages
```

Assistant 메시지에는 추가로

```text
contract_id

document_id

vendor_name
```

등의 context를 저장한다.

예:

```text
라온벨 계약 해지 조건 알려줘
```

답변 이후

```text
context:
contract_id = xxx
vendor = 라온벨
```

저장.

다음 질문:

```text
그럼 계약금은?
```

→ 이전 context를 보고 라온벨 계약으로 연결한다.

---


# 18. 현재 구현 상태 요약

## 구현 완료

```text
계약서 업로드

AI 계약서 분석

사용자 검토

계약 확정

계약 RAG 인덱싱

Seed RAG

Tool/RAG 라우팅

대화 History 저장

이전 계약 Context 유지

WeddingPlan 기반 데이터 격리

Citation 표시

재무 계산
```

---

## 부분 구현

```text
Seed 삭제 동기화

이미지/OCR 기반 RAG

대화 History UI 복원

계약 수정 후 RAG 동기화
```

---

## 미구현

```text
실제 사용자 인증

LangGraph Checkpointer

외부 Durable Queue

Chat History 조회 API
```

---



## 한 문장으로 설명하면

**MAIRRY는 사용자가 업로드한 결혼 계약서를 AI가 구조화하고, 계약·납부 정보는 DB Tool로 정확하게 조회하며, 해지·환불·위약금 같은 계약 조항은 RAG로 검색해 근거와 함께 답변하는 웨딩 금융 AI 서비스다.**

이 정도 구조로 정리하면 **README, 발표 자료, 프로젝트 설명 문서**에도 그대로 활용하기 좋다.
