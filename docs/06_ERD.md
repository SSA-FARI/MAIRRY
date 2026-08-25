# 06. ERD

## 관계

~~~mermaid
erDiagram
    USER ||--|| WEDDING_PLAN : owns
    USER ||--o{ DOCUMENT : uploads
    WEDDING_PLAN ||--o{ CONTRACT : contains
    DOCUMENT ||--o| CONTRACT : becomes
    CONTRACT ||--o{ PAYMENT : has

    USER {
      uuid id PK
      string display_name
      datetime created_at
    }
    WEDDING_PLAN {
      uuid id PK
      uuid user_id FK
      date wedding_date
      bigint available_asset
      datetime created_at
      datetime updated_at
    }
    DOCUMENT {
      uuid id PK
      uuid user_id FK
      string original_name
      string storage_key
      string mime_type
      string status
      json extraction_result
      string analysis_source
      string error_message
      datetime created_at
      datetime updated_at
    }
    CONTRACT {
      uuid id PK
      uuid wedding_plan_id FK
      uuid document_id FK
      string document_type
      string company
      bigint total_price
      json cancellation_terms
      string status
      datetime confirmed_at
      datetime created_at
      datetime updated_at
    }
    PAYMENT {
      uuid id PK
      uuid contract_id FK
      string name
      bigint amount
      date due_date
      string payment_status
      string source_text
      datetime created_at
      datetime updated_at
    }
~~~

## 상태값

### Document.status

~~~text
UPLOADED → PROCESSING → REVIEW_REQUIRED → CONFIRMED
                    ↘ FAILED ──(직접 입력)──→ CONFIRMED
~~~

### Contract.status

- DRAFT: AI 결과를 검수 중
- CONFIRMED: 사용자가 확정했으며 계산에 포함

### Payment.payment_status

- PAID
- UNPAID
- UNKNOWN

## 저장 원칙

- 금액은 원 단위 BIGINT로 저장한다.
- 날짜는 시간대가 없는 DATE로 저장한다.
- 원본 AI 결과는 Document.extraction_result에 보존한다.
- 사용자 수정값은 Contract와 Payment에 저장한다.
- Contract.status가 CONFIRMED인 Payment만 대시보드 계산에 사용한다.
- due_date가 없는 항목은 합계에는 포함할 수 있지만 타임라인의 확인 필요 영역에 표시한다.
- analysis_source는 LIVE_AI 또는 DEMO_FALLBACK이다.

## 인덱스

- DOCUMENT(user_id, created_at)
- CONTRACT(wedding_plan_id, status)
- PAYMENT(contract_id, due_date)

## 삭제

- Document 삭제 시 연결된 DRAFT 계약은 함께 삭제할 수 있다.
- CONFIRMED 계약이 연결된 문서는 직접 삭제하지 않고 계약 삭제 확인을 먼저 받는다.
- MVP에서는 soft delete를 구현하지 않아도 되지만 원본과 관계 데이터 삭제 순서를 지킨다.
