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

## 테이블 명세서
## users

### 역할

서비스에 가입하고 로그인하는 **개별 사용자**를 저장한다.

결혼을 두 사람이 함께 준비하더라도 하나의 계정을 공유하지 않고 각각 자신의 계정을 가진다.

```
USER A ─┐
        ├─ WeddingPlan
USER B ─┘
```

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 사용자 식별자 |
| `login_id` | VARCHAR(50) | X | UNIQUE | 로그인 ID |
| `password_hash` | VARCHAR(255) | X | - | 암호화된 비밀번호 |
| `display_name` | VARCHAR(50) | X | - | 사용자 표시 이름 |
| `email` | VARCHAR(255) | O | UNIQUE | 사용자 이메일 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 가입일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 정보 수정일 |

### 특징

BCrypt 등을 이용한 Hash를 저장한다.

```
password_hash = "$2a$10$..." ✅
```

Spring Security를 사용한다면 `BCryptPasswordEncoder`를 사용할 수 있다.

---

## wedding_plans

### 역할

서비스에서 가장 중요한 **최상위 도메인**이다.

한 쌍의 예비부부가 준비하고 있는 하나의 결혼을 의미한다.

```
WeddingPlan

├─ 두 명의 사용자
├─ 자산
├─ 웨딩홀
├─ 스드메
├─ 가전
├─ 계약서
├─ 지급일정
└─ AI 검색 범위
```

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 결혼계획 식별자 |
| `wedding_date` | DATE | O | - | 결혼 예정일 |
| `status` | ENUM | X | DEFAULT ACTIVE | 결혼계획 상태 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 생성일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 수정일 |

#### `status`

| 값 | 의미 |
| --- | --- |
| `ACTIVE` | 결혼 준비 진행 중 |
| `COMPLETED` | 결혼 완료 |

### 특징

wedding_plans에 `user_id`를 직접 넣지 않는 것이 핵심이다.

```
wedding_plans.user_id ❌
```

결혼 계획에는 두 사람이 참여하므로 별도의 wedding_plan_members에서 연결한다.

---

## wedding_plan_members

### 역할

`User`와 `WeddingPlan` 사이의 N:M 관계를 관리한다.

```
User A
   \
    WeddingPlan
   /
User B
```

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | WeddingPlan Member 식별자 |
| `wedding_plan_id` | UUID | X | FK | 참여 WeddingPlan |
| `user_id` | UUID | X | FK | 참여 사용자 |
| `role` | ENUM | X | - | OWNER / PARTNER |
| `joined_at` | TIMESTAMPTZ | X | DEFAULT now() | 참여일 |

### UNIQUE

```text
(wedding_plan_id, user_id)
```

동일 사용자가 같은 WeddingPlan에 중복 참여하는 것을 방지한다.

### `role`

| 값 | 설명 |
| --- | --- |
| `OWNER` | WeddingPlan 최초 생성자 |
| `PARTNER` | 상대방 사용자 |

#### 특징

`HUSBAND`, `WIFE`처럼 성별을 기준으로 설계하지 않는다.

또한 **WeddingPlan당 최대 2명**이라는 제한은 MVP에서는 DB Constraint보다는 서비스 로직에서 검증하는 것을 권장한다.

```
if (memberCount>=2) {
	thrownewWeddingPlanMemberLimitException();
}
```

---

## assets

### 역할

예비부부가 **결혼 준비에 실제 사용할 수 있는 자금**을 저장한다.

예:

```
본인 현금        2,000만원
본인 예적금      1,500만원
파트너 현금      1,000만원
공동 결혼통장    1,500만원

총 가용자금      6,000만원
```

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 자산 식별자 |
| `wedding_plan_id` | UUID | X | FK | WeddingPlan |
| `owner_member_id` | UUID | O | FK | PERSONAL이면 필수, JOINT이면 NULL |
| `owner_type` | ENUM | X | CHECK | PERSONAL / JOINT |
| `category` | ENUM | X | - | CASH / SAVINGS |
| `amount` | BIGINT | X | CHECK >= 0 | 자산 금액 |
| `label` | VARCHAR(100) | O | - | 사용자 지정 이름 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 생성일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 수정일 |

### `owner_type`

| 값 | 의미 |
| --- | --- |
| `PERSONAL` | 한 명에게 속한 자산 |
| `JOINT` | 두 사람의 공동 자산 |

### `category`

| 값 | 의미 |
| --- | --- |
| `CASH` | 현금성 자산 |
| `SAVINGS` | 예·적금 |

### 특징

MVP에서는 `월소득`, `대출`을 이 테이블에 섞지 않는 것이 좋다.

왜냐하면:

```
현금/예적금 → 자산
월소득      → 현금 흐름
대출        → 부채
```

로 의미가 다르기 때문이다.

향후 금융기능 확대 시 `incomes`, `liabilities`를 추가할 수 있다.

### 무결성 제약

```sql
CHECK (
  (owner_type = 'PERSONAL' AND owner_member_id IS NOT NULL)
  OR
  (owner_type = 'JOINT' AND owner_member_id IS NULL)
)
```

또한 개인 자산의 `owner_member_id`는 반드시 해당 `asset.wedding_plan_id`와 동일한 WeddingPlan 소속이어야 하며, 이 일치 여부는 서비스 레이어에서 검증한다.

---

## spending_items

### 역할

WeddingPlan에서 발생하는 **하나의 결혼 관련 지출**을 표현한다.

이 테이블이 결혼비용 관리의 핵심이다.

예:

```
WeddingPlan
 ├─ 웨딩홀
 ├─ 스드메
 ├─ 신혼여행
 ├─ 가전
 ├─ 가구
 └─ 신혼집
```

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 지출 항목 식별자 |
| `wedding_plan_id` | UUID | X | FK | WeddingPlan |
| `category` | VARCHAR(50) | X | - | 지출 카테고리 |
| `title` | VARCHAR(200) | O | - | 사용자에게 보여줄 제목 |
| `vendor_name` | VARCHAR(200) | O | - | 업체명 |
| `source_type` | ENUM | X | - | 데이터 발생 출처 |
| `total_amount` | BIGINT | O | CHECK >= 0 | 총 지출 금액 |
| `status` | ENUM | X | DEFAULT DRAFT | 지출 상태 |
| `confirmed_by_member_id` | UUID | O | FK | AI 결과 검수 사용자 |
| `confirmed_at` | TIMESTAMPTZ | O | - | 확정일 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 생성일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 수정일 |

### `category`

MVP에서는 실제로 `WEDDING_HALL`만 사용하더라도 다음 확장을 고려할 수 있다.

```
WEDDING_HALL
SDM
HONEYMOON
HOUSING
APPLIANCE
FURNITURE
OTHER
```

### `source_type`

| 값 | 설명 |
| --- | --- |
| `CONTRACT` | 계약서에서 생성 |
| `QUOTE` | 견적서에서 생성 |
| `RESERVATION` | 예약내역에서 생성 |
| `MANUAL` | 사용자 직접 입력 |

#### `status`

| 값 | 설명 |
| --- | --- |
| `DRAFT` | 직접 입력 등 임시 지출 정보 |
| `CONFIRMED` | 사용자 검수 완료 |
| `COMPLETED` | 지출 완료 |
| `CANCELLED` | 취소 |

### 특징

계약서가 없는 가전 견적, 여행 예약, 직접 입력 비용까지 동일한 구조로 확장할 수 있다.

검수자는 반드시 해당 지출과 동일한 WeddingPlan 소속이어야 하며, 이 일치 여부는 서비스 레이어에서 검증한다.

---

## payments

#### 역할

하나의 SpendingItem에서 발생하는 **실제 지급 일정**을 저장한다.

예를 들어 웨딩홀 총비용이 2,300만 원이라면:

```
웨딩홀 23,000,000

├─ 계약금
│   3,000,000
│   PAID
│
└─ 잔금
    20,000,000
    2027-04-30
    UNPAID
```

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 지급항목 식별자 |
| `spending_item_id` | UUID | X | FK | 소속 SpendingItem |
| `label` | VARCHAR(100) | X | - | 계약금/중도금/잔금 등 |
| `amount` | BIGINT | X | NOT NULL, CHECK >= 0 | 지급금액 |
| `due_date` | DATE | O | - | 지급 예정일 |
| `status` | ENUM | X | DEFAULT UNPAID | 지급 상태 |
| `paid_at` | DATE | O | - | 실제 지급일 |
| `source_text` | TEXT | O | - | 해당 정보를 추출한 원문 |
| `source_page` | INT | O | - | 근거 페이지 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 생성일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 수정일 |

### `status`

| 값 | 설명 |
| --- | --- |
| `UNPAID` | 미지급 |
| `PAID` | 지급 완료 |
| `CANCELLED` | 지급 취소 |

### 특징

`payments`는 사용자가 확정한 지급 데이터이므로 `amount`는 반드시 존재해야 한다.
AI가 금액을 찾지 못한 경우에는 확정 전에 사용자가 값을 입력하도록 한다.

이 테이블을 기준으로 **Wedding Financial Timeline**을 만들 수 있다.

```
ORDERBY due_date
```

또한 남은 지출 계산도 여기서 한다.

```
SUM(UNPAID payments)
```

---

## spending_terms

#### 역할

계약서 또는 견적서에 존재하는 **금액 이외의 중요한 조건**을 저장한다.

예:

- 취소조건
- 환불조건
- 위약금
- 보증인원
- 인원 변경기한
- 추가비용
- 식사 조건

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 계약조건 식별자 |
| `spending_item_id` | UUID | X | FK | 소속 지출 |
| `term_type` | VARCHAR(50) | X | - | 조건 종류 |
| `content` | TEXT | X | - | 정리된 조건 |
| `source_text` | TEXT | O | - | 계약서 원문 |
| `source_page` | INT | O | - | 근거 페이지 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 생성일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 수정일 |

### `term_type` 예시

```
CANCELLATION
REFUND
PENALTY
GUARANTEED_GUESTS
CHANGE_DEADLINE
ADDITIONAL_COST
OTHER
```

#### 예시

```
term_type
CANCELLATION

content
예식 90일 전까지 취소 시 계약금 전액 환불

source_text
계약일로부터 예식 90일 전까지 취소 시 계약금을 전액 환불한다.

source_page
3
```

### 특징

`spending_items.cancellation_policy`처럼 하나의 TEXT 필드에 모든 조건을 넣지 않는다.

따라서 향후:

> "보증인원 몇 명이야?"
> 

> "취소조건 알려줘."
> 

> "추가비용 조건 있어?"
> 

같은 AI 질문을 더 쉽게 처리할 수 있다.

---

## documents

### 역할

사용자가 업로드하는 **원본 계약서 또는 견적서**와 AI 최초 분석결과를 관리한다.

실제 PDF/JPG/PNG 파일 자체는 Object Storage에 저장하고 DB에는 경로를 저장한다.

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | 문서 식별자 |
| `wedding_plan_id` | UUID | X | FK | 소유 WeddingPlan |
| `spending_item_id` | UUID | O | FK | 확정 후 연결되는 지출 |
| `uploaded_by_member_id` | UUID | X | FK | 문서 업로드 Member |
| `document_type` | VARCHAR(50) | O | - | 문서 종류 |
| `original_filename` | VARCHAR(255) | X | - | 원본 파일명 |
| `file_url` | TEXT | X | - | Object Storage 경로 |
| `content_type` | VARCHAR(100) | O | - | MIME Type |
| `extraction_raw` | JSONB | O | - | AI 최초 분석 결과 |
| `analysis_status` | ENUM | X | DEFAULT UPLOADED | AI 분석 상태 |
| `analysis_source` | ENUM | X | DEFAULT LIVE_AI | LIVE_AI / DEMO_FALLBACK |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 업로드일 |
| `updated_at` | TIMESTAMPTZ | X | DEFAULT now() | 수정일 |

### `analysis_status`

```
UPLOADED
   ↓
ANALYZING
   ↓
PENDING_REVIEW
   ↓
CONFIRMED
```

실패:

```
ANALYZING
   ↓
FAILED
```

### 특징

`spending_item_id`는 Nullable이어야 한다.

문서 업로더는 반드시 해당 문서와 동일한 WeddingPlan 소속이어야 하며, 연결되는 SpendingItem도 동일한 WeddingPlan 소속이어야 한다. 두 일치 여부는 서비스 레이어에서 검증한다.

`spending_item_id`에는 UNIQUE를 두지 않는다. 하나의 지출에 계약서·견적서·변경계약서 등 여러 근거 문서가 연결될 수 있도록 **SpendingItem 1 : N Document** 관계를 허용한다.

단, `CONFIRMED` 문서의 `spending_item_id`는 일반 수정 API에서 재연결할 수 없도록 서비스 레이어에서 제한한다.

처음 업로드할 때는:

```
Document 생성

spending_item_id = NULL
```

AI가 문서를 분석하고 사용자가 확정하면:

```
SpendingItem 생성
        ↓
Document.spending_item_id 연결
```

하는 구조다.

---

### `extraction_raw`의 역할

이 컬럼은 상당히 중요하다.

AI가 최초로 다음처럼 분석했다고 하자.

```
{
  "documentType":"WEDDING_HALL",
  "vendorName":"A웨딩홀",
  "totalAmount":23000000,
  "payments": [
    {
      "label":"잔금",
      "amount":22000000
    }
  ]
}
```

그런데 사용자가 검수해보니 실제 잔금은:

```
20,000,000원
```

이었다.

그러면:

```
documents.extraction_raw
→ 22,000,000

payments.amount
→ 20,000,000
```

이 된다.

즉:

```
AI가 읽은 값
        ↓
extraction_raw

사용자가 확인
        ↓
실제 서비스 데이터
        ↓
SpendingItem
Payment
SpendingTerm
```

이렇게 분리한다.

**금융 계산에서 `extraction_raw`를 직접 사용하면 안 된다.**

---

## document_chunks

### 역할

업로드된 계약서의 자연어 질의응답을 위한 **RAG 데이터**를 저장한다.

### 테이블 명세

| 컬럼 | 타입 | NULL | 제약조건 | 설명 |
| --- | --- | --- | --- | --- |
| `id` | UUID | X | PK | Chunk 식별자 |
| `wedding_plan_id` | UUID | X | FK | 소유 WeddingPlan |
| `document_id` | UUID | X | FK | 원본 문서 |
| `chunk_index` | INT | X | UNIQUE 조합 | Chunk 순서 |
| `page_number` | INT | O | - | 원본 페이지 |
| `content` | TEXT | X | - | Chunk 텍스트 |
| `embedding` | VECTOR(1536) | O | - | Embedding 벡터 |
| `created_at` | TIMESTAMPTZ | X | DEFAULT now() | 생성일 |

`document_chunks.wedding_plan_id`와 원본 `documents.wedding_plan_id`는 반드시 일치해야 하며, 이 일치 여부는 저장 시 서비스 레이어에서 검증한다.

## 권한 및 WeddingPlan 격리 원칙

- 모든 조회·수정·삭제 API는 요청 사용자가 해당 `wedding_plan_id`의 `wedding_plan_members`인지 먼저 검증한다.
- `uploaded_by_member_id`, `confirmed_by_member_id`, `owner_member_id`는 대상 리소스와 **동일한 WeddingPlan 소속**이어야 한다.
- ERD 관계는 단일 FK로 유지하고, WeddingPlan 소속 일치 여부는 서비스 레이어에서 검증한다.
- RAG 검색도 `wedding_plan_id`로 먼저 필터링한 뒤 벡터 유사도 검색을 수행한다.

## 저장 원칙

- 금액은 원 단위 BIGINT로 저장한다.
- 지급일·결혼일은 DATE, 생성·수정 시각은 TIMESTAMPTZ를 사용한다.
- AI 최초 분석 결과는 documents.extraction_raw에 JSONB로 저장한다.
- 사용자 확정값은 spending_items, payments, spending_terms에 저장한다.
- 금융 계산에는 확정된 SpendingItem의 Payment만 사용한다.
- Payment의 `amount`는 NOT NULL이며 0 이상이어야 한다.
- `SpendingItem.status = CONFIRMED` 전환 시 `total_amount`는 필수이며, `total_amount = SUM(payments.amount)`인지 검증한다.
- 위 금액 정합성 검증에 실패하면 확정 트랜잭션 전체를 롤백한다.
- due_date = NULL이어도 금액이 확정되면 지출 합계에는 포함하고, 타임라인에서는 지급일 확인 필요로 표시한다.
- AI 장애 대응이 필요하면 analysis_source = LIVE_AI / DEMO_FALLBACK으로 구분한다.

확정 처리
~~~text
사용자 확정
   ↓
SpendingItem / Payment 값 검증
- total_amount 필수
- 모든 Payment.amount 필수
- total_amount = SUM(Payment.amount)
   ↓
SpendingItem 생성
Payment 생성
SpendingTerm 생성
Document 연결 및 CONFIRMED 변경
~~~
위 과정은 하나의 트랜잭션으로 처리하며, 검증 또는 저장 중 하나라도 실패하면 전체 롤백한다.

## 인덱스 및 UNIQUE

- WEDDING_PLAN_MEMBERS(wedding_plan_id, user_id) UNIQUE
- ASSETS(wedding_plan_id)
- SPENDING_ITEMS(wedding_plan_id, status)
- PAYMENTS(spending_item_id, status, due_date)
- DOCUMENTS(wedding_plan_id, analysis_status, created_at)
- DOCUMENT_CHUNKS(wedding_plan_id)
- DOCUMENT_CHUNKS(document_id, chunk_index) UNIQUE

## 필수 검증 테스트

- SpendingItem 삭제 시 `documents.spending_item_id`만 NULL이 되고 `wedding_plan_id`는 유지되는지 확인한다.
- SpendingItem 확정 시 `total_amount != SUM(payments.amount)`이면 요청을 실패시키고 전체 트랜잭션이 롤백되는지 확인한다.

## 삭제

- 확정 전 Document 삭제 시 관련 DocumentChunk도 함께 삭제한다.
- SpendingItem 삭제 시 연결된 Payment, SpendingTerm도 함께 삭제한다.
- SpendingItem 삭제 시 `documents.spending_item_id`만 NULL로 변경하고 `documents.wedding_plan_id`는 유지한다. 복합 FK를 사용하지 않으므로 `ON DELETE SET NULL` 충돌을 피한다.
- 확정된 계약정보가 연결된 문서는 바로 삭제하지 않고 사용자 확인을 받는다.
- MVP에서는 soft delete를 구현하지 않아도 되지만 원본과 관계 데이터 삭제 순서를 지킨다.