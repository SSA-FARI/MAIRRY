# 07. API 명세

## 공통 규칙

- Base URL: /api
- Content-Type: application/json, 파일 업로드만 multipart/form-data
- 금액: 원 단위 정수
- 날짜: YYYY-MM-DD
- 데모 사용자는 서버의 DEMO_USER_ID로 식별

## 공통 오류

~~~json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "가용자금은 0원 이상이어야 합니다.",
    "details": {}
  }
}
~~~

| HTTP | 의미 |
|---|---|
| 400 | 입력 형식 오류 |
| 404 | 리소스 없음 |
| 409 | 현재 상태에서 처리 불가 |
| 413 | 파일 용량 초과 |
| 415 | 미지원 파일 |
| 422 | AI 결과 또는 필수값 검증 실패 |
| 500 | 서버 오류 |
| 502 | 외부 AI 오류 |

## Wedding Plan

### PUT /api/wedding-plan

요청:

~~~json
{
  "weddingDate": "2027-05-15",
  "availableAsset": 30000000
}
~~~

응답 200: 저장된 계획

### GET /api/wedding-plan

응답 200: 현재 사용자의 계획

## Documents

### POST /api/documents

- multipart field: file
- 허용 형식: application/pdf, image/jpeg, image/png

응답 201:

~~~json
{
  "id": "uuid",
  "originalName": "contract.pdf",
  "status": "UPLOADED"
}
~~~

### POST /api/documents/{documentId}/analyze

응답 200:

~~~json
{
  "documentId": "uuid",
  "status": "REVIEW_REQUIRED",
  "analysisSource": "LIVE_AI",
  "extraction": {
    "documentType": "WEDDING_HALL",
    "company": "A웨딩홀",
    "totalPrice": 23000000,
    "payments": [
      {
        "name": "잔금",
        "amount": 20000000,
        "dueDate": "2027-04-30",
        "status": "UNPAID",
        "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
      }
    ],
    "cancellationTerms": [],
    "warnings": []
  }
}
~~~

### GET /api/documents/{documentId}

응답: 문서 상태, 분석 결과, 오류 메시지

### PUT /api/documents/{documentId}/confirm

요청:

~~~json
{
  "documentType": "WEDDING_HALL",
  "company": "A웨딩홀",
  "totalPrice": 23000000,
  "payments": [
    {
      "name": "잔금",
      "amount": 20000000,
      "dueDate": "2027-04-30",
      "status": "UNPAID",
      "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
    }
  ],
  "cancellationTerms": []
}
~~~

검증:

- company 필수
- totalPrice와 payment.amount는 0 이상
- dueDate는 null 또는 유효한 날짜
- 확정 요청은 REVIEW_REQUIRED 또는 FAILED 상태에서만 허용

응답 200: 생성된 Contract와 Payment

## Contracts

### GET /api/contracts

응답 200:

~~~json
{
  "items": [
    {
      "id": "uuid",
      "company": "A웨딩홀",
      "totalPrice": 23000000,
      "status": "CONFIRMED",
      "nextPayment": {
        "name": "잔금",
        "amount": 20000000,
        "dueDate": "2027-04-30"
      }
    }
  ]
}
~~~

### GET /api/contracts/{contractId}

응답: 계약 정보, 지급항목, 취소조건, 문서 ID

## Finance

### GET /api/finance/summary

응답 200:

~~~json
{
  "availableAsset": 30000000,
  "remainingExpense": 20000000,
  "expectedBalance": 10000000,
  "nearestPayment": {
    "contractId": "uuid",
    "company": "A웨딩홀",
    "name": "잔금",
    "amount": 20000000,
    "dueDate": "2027-04-30"
  },
  "timeline": []
}
~~~

계산 대상: CONFIRMED 계약의 UNPAID 지급항목

### POST /api/finance/simulate

요청:

~~~json
{
  "name": "가전 추가 구매",
  "amount": 3000000
}
~~~

응답 200:

~~~json
{
  "currentExpectedBalance": 10000000,
  "simulatedExpectedBalance": 7000000,
  "shortageAmount": 0
}
~~~

## Chat

### POST /api/chat

요청:

~~~json
{
  "message": "웨딩홀 잔금일이 언제야?"
}
~~~

응답 200:

~~~json
{
  "answer": "A웨딩홀 잔금일은 2027년 4월 30일입니다.",
  "answerType": "CONTRACT",
  "citations": [
    {
      "contractId": "uuid",
      "label": "A웨딩홀 · 잔금",
      "sourceText": "잔금 20,000,000원은 2027년 4월 30일까지"
    }
  ],
  "calculation": null
}
~~~

answerType:

- CONTRACT: 계약 원문 근거
- CALCULATION: 서버 계산 결과
- NOT_FOUND: 확인 가능한 정보 없음

## Chat 내부 Tool 계약

Chat Orchestrator는 사용자 질문을 분류한 뒤 다음 서버 Tool을 호출한다. Tool은 애플리케이션 내부 서비스 함수이며 외부 사용자에게 직접 노출하지 않아도 된다.

### 공통 ToolResult

~~~json
{
  "status": "SUCCESS",
  "toolName": "getFinanceSummary",
  "data": {},
  "evidence": [],
  "calculatedAt": "2026-08-25T12:00:00+09:00",
  "error": null
}
~~~

status:

- SUCCESS
- NOT_FOUND
- INSUFFICIENT_DATA
- INVALID_ARGUMENT
- TOOL_ERROR

### getFinanceSummary()

- 용도: 남은 지출, 예상 잔액, 부족액 질문
- 입력: 현재 사용자와 WeddingPlan Context
- 출력: availableAsset, remainingExpense, expectedBalance
- 기준: CONFIRMED 계약의 UNPAID 지급항목

### getUpcomingPayments()

입력:

~~~json
{
  "from": "2026-08-25",
  "to": null,
  "limit": 5,
  "contractId": null
}
~~~

출력:

~~~json
{
  "status": "SUCCESS",
  "toolName": "getUpcomingPayments",
  "data": {
    "payments": [
      {
        "contractId": "uuid",
        "company": "A웨딩홀",
        "name": "잔금",
        "amount": 20000000,
        "dueDate": "2027-04-30"
      }
    ]
  },
  "evidence": [],
  "calculatedAt": "2026-08-25T12:00:00+09:00",
  "error": null
}
~~~

### getContractDetails(contractId)

- 용도: 특정 계약의 지급조건·취소조건 질문
- 출력: 확정 계약, 지급항목, 취소조건, sourceText
- 계약을 식별할 수 없으면 NOT_FOUND를 반환

### simulateAdditionalExpense(name, amount)

- 용도: 추가 구매·예산 변경 질문
- amount는 0보다 큰 원 단위 정수
- 출력: currentExpectedBalance, simulatedExpectedBalance, shortageAmount
- 필요한 WeddingPlan이 없으면 INSUFFICIENT_DATA를 반환

### Chat 응답 규칙

- AI는 ToolResult의 금액·날짜를 그대로 사용한다.
- 계산 질문 응답에는 toolName, calculatedAt, 계산 결과를 포함한다.
- 일정 질문 응답에는 contractId, dueDate와 계약 근거를 포함한다.
- SUCCESS가 아니면 임의의 금액·날짜를 생성하지 않는다.
- 동일한 확정 데이터와 인자는 동일한 계산 결과를 반환해야 한다.

계산 질문 응답 예시:

~~~json
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
~~~
