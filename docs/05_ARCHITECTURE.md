# 05. 시스템 아키텍처

## 기술 스택 가안

| 영역 | 선택 |
|---|---|
| Frontend | Next.js + TypeScript |
| Backend | FastAPI + Python |
| Database | PostgreSQL |
| File Storage | S3 호환 객체 스토리지 |
| AI | backend/ai 내부 Python 패키지 + Vision/OCR 지원 LLM |
| API | REST/JSON |
| 배포 | 프론트와 API를 각각 관리형 서비스에 배포 |

외부 서비스는 환경변수와 어댑터로 분리해 교체할 수 있게 한다.

## 구성

~~~text
[Browser / Next.js]
        |
        | REST API
        v
[FastAPI Application]
   |        |          |
   |        |          +-- [backend/ai] -- Vision LLM
   |        +------------- [Object Storage]
   +---------------------- [PostgreSQL]
~~~

## 주요 컴포넌트

### Frontend

- 초기 설정과 금융 대시보드
- 문서 업로드 및 분석 상태 표시
- AI 추출 결과 검수
- 계약·지급 타임라인 조회
- 추가지출 시뮬레이션
- AI 질문과 근거 표시

### Backend

- 입력 검증과 데모 사용자 식별
- 파일 메타데이터·계약·지급항목 저장
- 문서 분석 요청과 상태 관리
- 확정값 기반 자금 계산
- AI 질문용 안전한 Context 구성

### Backend AI Package

- 파일을 Vision LLM에 전달
- 고정 스키마의 JSON 반환
- 근거 문장과 확인 필요 항목 반환
- 모델 응답 검증 및 실패 정규화
- AI가 계산하지 않도록 계산 결과를 Context로 전달
- 독립 서버로 배포하지 않고 FastAPI가 공개 인터페이스를 import
- backend/app/domains를 직접 import하지 않고 Tool 요청만 반환

## 문서 처리 흐름

~~~text
1. Frontend → Backend: 파일 업로드
2. Backend → Storage: 원본 저장
3. Backend: Document 상태를 PROCESSING으로 변경
4. Backend → AI Adapter: 파일 분석 요청
5. AI Adapter → Backend: 구조화 결과 반환
6. Backend: 추출 결과 저장, 상태를 REVIEW_REQUIRED로 변경
7. Frontend: 결과 조회 및 사용자 수정
8. Frontend → Backend: 확정 요청
9. Backend: Contract·Payment 저장, 상태를 CONFIRMED로 변경
10. Backend: 대시보드 요약 재계산
~~~

3일 MVP에서는 분석 요청을 동기 처리할 수 있다. 응답이 길어질 경우 분석 요청 후 상태를 조회하는 단순 폴링 방식으로 전환한다.

## 자금 계산 경계

- 입력: WeddingPlan.availableAsset, CONFIRMED 상태의 UNPAID Payment
- 출력: remainingExpense, expectedBalance, nearestPayment
- 시뮬레이션은 DB에 저장하지 않고 요청별로 계산한다.
- LLM 출력값으로 합계나 잔액을 저장하지 않는다.

## AI 대화와 Tool Calling

금액·일정 질문은 LLM이 직접 계산하거나 원문에서 임의로 판단하지 않는다. AI는 질문의 의도를 분류하고 필요한 서버 Tool을 호출한 뒤, 반환 결과를 사용자에게 설명한다.

~~~text
사용자 질문
  → Chat Orchestrator: 의도·필수 인자 확인
  → Backend Tool 호출
  → 확정 데이터 조회 또는 결정론적 계산
  → 구조화된 ToolResult 반환
  → AI가 금액·날짜를 변경하지 않고 자연어로 설명
~~~

### Tool 분류

| 질문 유형 | 호출 Tool | 데이터 기준 |
|---|---|---|
| 남은 지출·예상 잔액 | getFinanceSummary | 확정된 미지급 항목 |
| 다음 결제·잔금일 | getUpcomingPayments | 확정된 지급일 |
| 특정 계약 조건 | getContractDetails | 확정 계약과 근거 문장 |
| 추가 구매 가능 여부 | simulateAdditionalExpense | 서버 시뮬레이션 |

### ToolResult 상태

- SUCCESS: 결과와 기준 데이터를 반환
- NOT_FOUND: 요청한 계약·일정이 없음
- INSUFFICIENT_DATA: 계산에 필요한 확정 데이터가 부족함
- INVALID_ARGUMENT: 금액·날짜 등 인자가 유효하지 않음
- TOOL_ERROR: 조회·계산에 실패함

### 응답 불변 규칙

- AI는 Tool이 반환한 금액과 날짜를 다시 계산하거나 변경하지 않는다.
- 결과에는 계산 기준 시각과 포함된 계약 또는 근거를 표시한다.
- SUCCESS가 아니면 AI가 값을 추측하지 않고 상태에 맞는 안내를 제공한다.
- 사용자가 한 질문에 여러 Tool이 필요하면 조회 후 계산 순서로 호출한다.
- 일반적인 계약 설명은 가능하지만 법률적 판단으로 확장하지 않는다.

## 보안·개인정보 최소 기준

- 허용 확장자와 MIME type을 모두 확인한다.
- 파일명은 서버에서 생성하고 원본 이름은 메타데이터로만 보관한다.
- 로그에 계약 원문·금액·개인정보를 출력하지 않는다.
- 저장소 파일은 공개 URL로 제공하지 않는다.
- 사용자 범위로 문서·계약 조회를 제한한다.
- 주민등록번호·계좌번호 등 계산에 불필요한 값은 추출 스키마에서 제외한다.

## Fallback

- 샘플 문서 해시와 사전 분석 JSON을 준비한다.
- 외부 AI 장애 시 샘플 문서에 한해 Fallback 결과를 반환한다.
- Fallback 사용 여부를 응답 메타데이터와 화면에 표시한다.

## 환경변수

~~~text
DATABASE_URL
OBJECT_STORAGE_BUCKET
OBJECT_STORAGE_ENDPOINT
OBJECT_STORAGE_ACCESS_KEY
OBJECT_STORAGE_SECRET_KEY
AI_API_KEY
AI_MODEL
AI_BASE_URL
AI_TIMEOUT_SECONDS
DEMO_USER_ID
DEMO_USER_LOGIN_ID
DEMO_USER_DISPLAY_NAME
DEMO_USER_EMAIL
ENABLE_DEMO_FALLBACK
~~~
