# 07. API 명세

## 목적과 기준

MAIRRY MVP REST API의 동작, 검증, 상태 전이를 정의한다. 기계 판독 계약의 Source of Truth는
`contracts/openapi.yaml`이다. 공개 API 변경은 OpenAPI → 이 문서 → Backend → Frontend → 테스트
순서로 반영한다.

## 공통 규칙

| 항목 | 규칙 |
|---|---|
| Base URL | `/api` |
| JSON | `application/json`, 외부 필드는 camelCase |
| 파일 | `multipart/form-data`, field 이름 `file` |
| 사용자 | 서버의 `DEMO_USER_ID`; 요청에서 `userId`를 받지 않음 |
| 금액 | 원 단위 정수 |
| 날짜/시각 | `YYYY-MM-DD` / timezone 포함 ISO 8601 |
| ID | UUID 문자열 |
| 추가 필드 | 스키마에 없는 요청 필드는 거부 |

계약 목록은 최근 확정순, 지급 타임라인은 `dueDate ASC`와 안정적인 보조키 순으로 반환한다.

## 공통 오류

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "가용자금은 0원 이상이어야 합니다.",
    "details": {}
  }
}
```

| HTTP | 대표 code | 의미 |
|---:|---|---|
| 400 | VALIDATION_ERROR | 요청 값/형식 오류 |
| 404 | RESOURCE_NOT_FOUND | 현재 사용자 범위에 리소스 없음 |
| 409 | INVALID_STATE | 현재 상태에서 처리 불가 |
| 413 | FILE_TOO_LARGE | 업로드 용량 초과 |
| 415 | UNSUPPORTED_MEDIA_TYPE | 확장자 또는 MIME 미지원 |
| 422 | EXTRACTION_VALIDATION_ERROR | 확정 데이터 검증 실패 |
| 500 | INTERNAL_ERROR | 서버 오류 |
| 502 | AI_PROVIDER_ERROR | 외부 AI 실패, Fallback 불가 |

다른 사용자의 ID는 존재 여부를 노출하지 않고 404를 반환한다. `details`에 계약 원문, 저장소 키,
비밀값, 내부 예외문을 포함하지 않는다.

## 엔드포인트 요약

| Method | Path | 성공 | 설명 |
|---|---|---:|---|
| GET | `/health` | 200 | 상태 확인 |
| POST | `/v1/auth/demo-login` | 200 | 설정된 단일 Demo User 조회·초기화 |
| GET | `/wedding-plan` | 200 | 계획 조회 |
| PUT | `/wedding-plan` | 200 | 계획 생성/수정 |
| POST | `/documents` | 201 | 문서 업로드 |
| GET | `/documents/{documentId}` | 200 | 문서/분석 상태 조회 |
| POST | `/documents/{documentId}/analyze` | 202 | 분석 시작/재시도 |
| PUT | `/documents/{documentId}/confirm` | 200 | 계약 확정 |
| GET | `/contracts` | 200 | 계약 목록 |
| GET | `/contracts/{contractId}` | 200 | 계약 상세 |
| GET | `/finance/summary` | 200 | 금융 요약/타임라인 |
| POST | `/finance/simulate` | 200 | 저장 없는 시뮬레이션 |
| POST | `/chat` | 200 | 근거 기반 답변 |

## Health

### GET /api/health

응답 200: `{"status": "ok"}`

## Demo Login

### POST /api/v1/auth/demo-login

JWT, Cookie, Session 없이 서버 설정의 단일 `DEMO_USER_ID`만 조회하는 공개 MVP 시연용 API다.
실제 보안 인증이나 일반 사용자 로그인으로 사용하지 않는다. 요청 본문, Query, Header에서 사용자
ID나 로그인 정보를 받지 않는다.

Demo User가 없으면 `DEMO_USER_ID`, `DEMO_USER_LOGIN_ID`, `DEMO_USER_DISPLAY_NAME`,
`DEMO_USER_EMAIL` 설정으로 한 번만 생성한다. `password_hash`에는 요청 시 생성하고 즉시 폐기한 임의
비밀번호의 bcrypt 해시만 저장한다. 이미 존재하는 사용자의 프로필과 해시는 덮어쓰지 않는다.

요청 본문: 없음.

응답 200:

```json
{
  "user": {
    "id": "00000000-0000-0000-0000-000000000001",
    "loginId": "demo",
    "displayName": "Demo User",
    "email": null
  },
  "mode": "DEMO"
}
```

응답에는 `passwordHash`, 환경변수 이름·설정 원문, JWT, Refresh Token을 포함하지 않는다.
Demo 설정이 누락되거나 잘못된 경우 애플리케이션 시작을 거부한다. 설정과 DB UNIQUE 데이터가
충돌하거나 저장에 실패하면 민감한 설정값을 노출하지 않는 공통 500 오류를 반환한다.

## Wedding Plan

### PUT /api/wedding-plan

요청:

```json
{"weddingDate": "2027-05-15", "availableAsset": 30000000}
```

`weddingDate`는 유효한 날짜, `availableAsset`은 0 이상 9,223,372,036,854,775,807 이하의
원 단위 int64(BIGINT) 정수
(`0`~`9,223,372,036,854,775,807`)다.

WeddingPlan의 `availableAsset`은 초기 설정에서 입력한 대표 공동 현금 자산 한 건을 의미한다.
PERSONAL 자산과 별도로 추가한 JOINT 자산은 이 값에 합산하지 않으며 Finance Summary의
`availableAsset`에서 전체 자산 합계로 제공한다.

응답 200:

```json
{
  "id": "7d985a2f-13ab-4fab-a3d7-d3ca8d696977",
  "weddingDate": "2027-05-15",
  "availableAsset": 30000000
}
```

오류: 400.

### GET /api/wedding-plan

응답 200은 PUT 응답과 같다. 계획이 없으면 404.

## Documents

### POST /api/documents

PDF/JPG/PNG 한 건을 업로드한다. 확장자와 실제 MIME을 모두 검증하며 원본은 비공개 객체로
저장한다. 최대 용량은 배포 설정값을 따르고 UI와 API가 같은 값을 사용한다.

요청: `multipart/form-data`, `file` 필수.

응답 201:

```json
{
  "id": "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
  "originalName": "contract.pdf",
  "status": "UPLOADED"
}
```

오류: 413, 415.

### POST /api/documents/{documentId}/analyze

UPLOADED 또는 FAILED 문서를 PROCESSING으로 바꾸고 분석을 시작한다. Frontend는 1초 간격으로
문서를 조회하며 60초 UI 타임아웃은 서버 작업을 취소하지 않는다.

응답 202:

```json
{
  "id": "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
  "originalName": "contract.pdf",
  "status": "PROCESSING",
  "analysisSource": null,
  "extraction": null,
  "error": null
}
```

오류: 문서 없음 404, PROCESSING/REVIEW_REQUIRED/CONFIRMED 상태 409. 접수 뒤 Provider가 실패하면
폴링 결과가 FAILED가 된다. 즉시 실패하고 Fallback도 불가능한 구현은 502를 사용할 수 있다.

### GET /api/documents/{documentId}

| status | analysisSource | extraction | error |
|---|---|---|---|
| UPLOADED | null | null | null |
| PROCESSING | null | null | null |
| REVIEW_REQUIRED | LIVE_AI/DEMO_FALLBACK | object | null |
| FAILED | null 또는 시도 source | null | ErrorBody |
| CONFIRMED | LIVE_AI/DEMO_FALLBACK | object | null |

분석 성공 응답 200:

```json
{
  "id": "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
  "originalName": "contract.pdf",
  "status": "REVIEW_REQUIRED",
  "analysisSource": "LIVE_AI",
  "extraction": {
    "documentType": "WEDDING_HALL",
    "company": "A웨딩홀",
    "totalPrice": 23000000,
    "payments": [{
      "name": "잔금",
      "amount": 20000000,
      "dueDate": "2027-04-30",
      "status": "UNPAID",
      "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
    }],
    "cancellationTerms": [],
    "warnings": []
  },
  "error": null
}
```

오류: 404.

### PUT /api/documents/{documentId}/confirm

검수값으로 Contract와 Payment를 만들고 Document를 CONFIRMED로 변경한다. WeddingPlan이 먼저
존재해야 하며 전체 작업은 한 DB 트랜잭션이다.

요청:

```json
{
  "documentType": "WEDDING_HALL",
  "company": "A웨딩홀",
  "totalPrice": 23000000,
  "payments": [{
    "name": "잔금",
    "amount": 20000000,
    "dueDate": "2027-04-30",
    "status": "UNPAID",
    "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
  }],
  "cancellationTerms": [{
    "summary": "예식 90일 전까지 계약금 환급",
    "sourceText": "예식일 90일 전까지 취소 시 계약금 전액 환급"
  }]
}
```

검증:

- REVIEW_REQUIRED 또는 직접 입력 경로의 FAILED 상태만 허용
- company와 payment.name은 공백이 아닌 문자열
- totalPrice는 0 이상
- WEDDING_HALL 확정 요청은 payment가 1개 이상이어야 함
- 확정 요청의 payment.amount는 0 이상 정수이며 null은 허용하지 않음
- dueDate는 null 또는 유효한 날짜
- AI 근거가 있는 sourceText는 원문을 보존하고, FAILED 직접입력처럼 근거가 없으면 null을 사용
- cancellationTerms는 빈 배열 가능

AI 추출 결과에서는 payment.amount가 null일 수 있지만 확정 요청에서는 사용자가 금액을 입력해야
한다. amount가 null이거나 payments가 비어 있으면 422로 확정을 차단한다. dueDate는 null이어도
금융 합계를 계산할 수 있으므로 확정을 허용한다. sourceText는 필드 자체를 생략하지 않고 AI
근거가 없는 수동 입력에서는 null로 전송한다.

응답 200은 Contract 상세 형식이다. 오류: 문서/계획 없음 404, 잘못된 상태/중복 확정 409,
필수값이나 구조 오류 422.

## Contracts

### GET /api/contracts

확정 계약만 반환한다. 빈 상태는 `200 {"items": []}`이다.

```json
{
  "items": [{
    "id": "90af8db0-a099-40a0-bb92-720ec331a6a0",
    "company": "A웨딩홀",
    "totalPrice": 23000000,
    "status": "CONFIRMED",
    "nextPayment": {
      "contractId": "90af8db0-a099-40a0-bb92-720ec331a6a0",
      "company": "A웨딩홀",
      "name": "잔금",
      "amount": 20000000,
      "dueDate": "2027-04-30"
    }
  }]
}
```

`nextPayment`는 금액/지급일이 있는 가장 가까운 미래 UNPAID 항목이며 없으면 null이다.

### GET /api/contracts/{contractId}

응답 200:

```json
{
  "id": "90af8db0-a099-40a0-bb92-720ec331a6a0",
  "documentId": "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
  "documentType": "WEDDING_HALL",
  "company": "A웨딩홀",
  "totalPrice": 23000000,
  "status": "CONFIRMED",
  "payments": [{
    "name": "잔금",
    "amount": 20000000,
    "dueDate": "2027-04-30",
    "status": "UNPAID",
    "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
  }],
  "cancellationTerms": []
}
```

오류: 404.

## Finance

### GET /api/finance/summary

CONFIRMED 계약의 금액이 있는 UNPAID 지급항목만 계산한다. 확정 전 추출값, PAID, UNKNOWN,
amount null 항목은 제외한다.

```json
{
  "availableAsset": 30000000,
  "remainingExpense": 20000000,
  "expectedBalance": 10000000,
  "nearestPayment": {
    "contractId": "90af8db0-a099-40a0-bb92-720ec331a6a0",
    "company": "A웨딩홀",
    "name": "잔금",
    "amount": 20000000,
    "dueDate": "2027-04-30"
  },
  "timeline": []
}
```

- `remainingExpense = SUM(payment.amount)`
- `availableAsset = SUM(asset.amount)`이며 현재 WeddingPlan의 모든 자산을 포함
- `expectedBalance = availableAsset - remainingExpense`
- 대상이 없으면 합계 0, nearestPayment null, timeline 빈 배열
- WeddingPlan이 없으면 404

### POST /api/finance/simulate

DB를 변경하지 않는 요청별 계산이다.

요청: `{"name": "가전 추가 구매", "amount": 3000000}`

응답 200:

```json
{
  "currentExpectedBalance": 10000000,
  "simulatedExpectedBalance": 7000000,
  "shortageAmount": 0
}
```

amount는 0보다 큰 정수다. `simulatedExpectedBalance = currentExpectedBalance - amount`,
`shortageAmount = max(0, -simulatedExpectedBalance)`이다. 오류: 요청 400, 계획 없음 404.

## Chat

### POST /api/chat

요청: `{"message": "웨딩홀 잔금일이 언제야?"}`

message는 공백이 아닌 1~2,000자 문자열이다. AI는 Backend ToolResult의 숫자, 날짜, 상태를
변경하거나 재계산하지 않는다.

계약 근거 응답:

```json
{
  "answer": "A웨딩홀 잔금일은 2027년 4월 30일입니다.",
  "answerType": "CONTRACT",
  "citations": [{
    "contractId": "90af8db0-a099-40a0-bb92-720ec331a6a0",
    "label": "A웨딩홀 · 잔금",
    "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
  }],
  "calculation": null
}
```

계산 응답:

```json
{
  "answer": "가전 비용 300만 원을 추가하면 예상 잔액은 700만 원이며 부족액은 없습니다.",
  "answerType": "CALCULATION",
  "citations": [],
  "calculation": {
    "toolName": "simulateAdditionalExpense",
    "currentExpectedBalance": 10000000,
    "simulatedExpectedBalance": 7000000,
    "shortageAmount": 0,
    "calculatedAt": "2026-08-25T12:00:00+09:00"
  }
}
```

answerType은 CONTRACT, CALCULATION, NOT_FOUND다. 지원하지 않는 질문과 Tool 실패에서는 임의의
금액/날짜를 생성하지 않는다. 요청 오류 400, AI 실패 및 대체 응답 불가 502.

## Chat 내부 Tool 계약

내부 Tool은 공개 REST API가 아니며 공통 결과는 `contracts/tool-result.schema.json`을 따른다.

```json
{
  "status": "SUCCESS",
  "toolName": "getFinanceSummary",
  "data": {},
  "evidence": [],
  "calculatedAt": "2026-08-25T12:00:00+09:00",
  "error": null
}
```

| status | 의미/응답 규칙 |
|---|---|
| SUCCESS | data/evidence만 근거로 설명 |
| NOT_FOUND | 대상 없음, 값 추측 금지 |
| INSUFFICIENT_DATA | 필요한 입력 안내 |
| INVALID_ARGUMENT | 올바른 입력 요청 |
| TOOL_ERROR | 일시 오류 안내, 값 추측 금지 |

### getFinanceSummary()

현재 사용자 Context를 받아 `availableAsset`, `remainingExpense`, `expectedBalance`를 Finance API와
동일한 규칙으로 반환한다.

### getUpcomingPayments(from, to, limit, contractId)

- from/to: nullable date, `from <= to`
- limit: 1 이상 정수, 기본 5
- contractId: nullable UUID, 현재 사용자 소유로 제한
- 지급일/금액이 있는 항목을 `dueDate ASC`로 반환

### getContractDetails(contractId)

현재 사용자의 확정 계약, 지급항목, 취소조건, sourceText를 반환한다. 식별 불가 또는 타 사용자
계약은 NOT_FOUND다.

### simulateAdditionalExpense(name, amount)

name은 공백이 아니고 amount는 0보다 큰 정수다. 현재/시뮬레이션 잔액과 부족액을 반환하며 DB를
변경하지 않는다. 계획이 없으면 INSUFFICIENT_DATA다.

## 테스트 매핑

| 영역 | `docs/09_TEST_SCENARIO.md` ID |
|---|---|
| 계획 | PLAN-01~02 |
| 업로드 | DOC-01~03 |
| 분석 | AI-01~03 |
| 확정 | REVIEW-01~06 |
| 금융 | FIN-01~04 |
| 대화/Tool | CHAT-01~10 |
