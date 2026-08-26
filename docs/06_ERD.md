# 06. ERD

![ERD](img/erd.png)

| 영역 | 역할 |
| --- | --- |
| `users` | 실제 로그인 사용자 |
| `wedding_plans` | 두 사람이 공유하는 결혼 준비 공간 |
| `wedding_plan_members` | 사용자와 WeddingPlan 연결 |
| `assets` | 결혼 준비에 사용할 자금 |
| `spending_items` | 웨딩홀·스드메 등 하나의 지출 단위 |
| `payments` | 계약금·중도금·잔금 등 실제 지급 일정 |
| `spending_terms` | 취소·환불·보증인원 등 계약조건 |
| `documents` | 원본 계약서/견적서와 AI 분석 결과 |
| `document_chunks` | 계약서 RAG 검색용 데이터 |


## 상태값

### Document.analysis_status

~~~text
UPLOADED → ANALYZING → REVIEW_REQUIRED → CONFIRMED
                    ↘ FAILED ──(직접 입력)──→ CONFIRMED
~~~

### SpendingItem.status

- CONFIRMED: 사용자 확정, 계산에 포함
- COMPLETED: 모든 지급 완료
- CANCELLED: 취소된 지출

### Payment.payment_status

- PAID
- UNPAID
- UNKNOWN
UNKNOWN은 저장하지 않고 사용자 검수 시 PAID / UNPAID 중 하나로 확정한다.

## 저장 원칙

- 금액은 원 단위 BIGINT로 저장한다.
- 지급일·결혼일은 DATE, 생성·수정 시각은 TIMESTAMPTZ를 사용한다.
- AI 최초 분석 결과는 documents.extraction_raw에 JSONB로 저장한다.
- 사용자 확정값은 spending_items, payments, spending_terms에 저장한다.
- 금융 계산에는 확정된 SpendingItem의 Payment만 사용한다.
- due_date = NULL이어도 금액이 확정되면 지출 합계에는 포함하고, 타임라인에서는 지급일 확인 필요로 표시한다.
- AI 장애 대응이 필요하면 analysis_source = LIVE_AI / DEMO_FALLBACK으로 구분한다.

확정 처리
~~~text
사용자 확정
   ↓
SpendingItem 생성
Payment 생성
SpendingTerm 생성
Document 연결 및 CONFIRMED 변경
~~~
위 과정은 하나의 트랜잭션으로 처리한다.

## 인덱스

- WEDDING_PLAN_MEMBERS(wedding_plan_id, user_id) UNIQUE
- ASSETS(wedding_plan_id)
- SPENDING_ITEMS(wedding_plan_id, status)
- PAYMENTS(spending_item_id, status, due_date)
- DOCUMENTS(wedding_plan_id, analysis_status, created_at)
- DOCUMENT_CHUNKS(wedding_plan_id)
- DOCUMENT_CHUNKS(document_id, chunk_index) UNIQUE

## 삭제

- 확정 전 Document 삭제 시 관련 DocumentChunk도 함께 삭제한다.
- SpendingItem 삭제 시 연결된 Payment, SpendingTerm도 함께 삭제한다.
- SpendingItem이 삭제되어도 원본 Document는 자동 삭제하지 않고 연결만 해제한다.
- 확정된 계약정보가 연결된 문서는 바로 삭제하지 않고 사용자 확인을 받는다.
- MVP에서는 soft delete를 구현하지 않아도 되지만 원본과 관계 데이터 삭제 순서를 지킨다.