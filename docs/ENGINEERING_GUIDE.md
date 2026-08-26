# MAIRRY Engineering Guide

이 문서는 MAIRRY의 코딩 컨벤션, 아키텍처 규칙, 표준 구현 예제를 정의하는 **유일한 공통 개발 규칙(Source of Truth)**이다. Codex는 AGENTS.md, Claude Code는 CLAUDE.md를 통해 이 문서를 읽는다.

## 1. 작업 시작 순서

1. docs/02_MVP_SCOPE.md에서 현재 범위와 Won't Have를 확인한다.
2. 이 문서를 읽고 담당 디렉터리의 경계를 확인한다.
3. API·데이터 변경이면 contracts와 docs/07_API_SPEC.md를 먼저 확인한다.
4. 작은 단위로 구현하고 담당 영역의 테스트를 실행한다.
5. 핵심 흐름이 바뀌면 docs/09_TEST_SCENARIO.md를 갱신한다.

문서와 구현이 충돌하면 실제 코드에 맞춰 임의 진행하지 말고 관련 계약 문서를 함께 수정한다.

구현 작업은 [10_IMPLEMENTATION_PLAN.md](10_IMPLEMENTATION_PLAN.md)의 선행관계와
[11_TEAM_OWNERSHIP.md](11_TEAM_OWNERSHIP.md)의 기능 소유권을 따른다. Git 작업과 리뷰는
[12_GIT_CONVENTION.md](12_GIT_CONVENTION.md)를 따른다.

## 1-1. 개발환경과 에이전트 독립성

- 운영체제, IDE, Codex, Claude Code 등 실행 주체와 관계없이 저장소의 계약과 완료 조건은 같다.
- 로컬 통합 실행의 기준 환경은 루트 `compose.yaml`이다. 로컬 직접 실행은 빠른 개발용 보조 경로다.
- 공통 명령은 저장소의 `scripts/`에 두고, 에이전트 전용 파일에는 링크와 진입 순서만 둔다.
- 특정 사용자의 절대 경로, 전역 Python·Node 설치, 이미 실행 중인 GUI나 셸 상태에 의존하지 않는다.
- 환경 차이로 명령을 바꿔도 생성되는 API, 데이터, 테스트 결과는 동일해야 한다.
- 자동화 도구는 작업 전 `git status`를 확인하고 다른 개발자의 변경을 덮어쓰지 않는다.
- 의존성 설치와 테스트는 동시에 같은 `node_modules`, `.venv`, DB volume을 수정하지 않는다.
- 비밀값은 `.env`에만 두고, 문서·프롬프트·로그·테스트 픽스처에 복사하지 않는다.

## 2. 기술 스택

| 영역          | 기준                                  |
| ------------- | ------------------------------------- |
| Frontend      | Next.js, React, TypeScript            |
| Backend       | FastAPI, Python 3.12, Pydantic        |
| Database      | PostgreSQL                            |
| Storage       | S3 호환 객체 스토리지                 |
| AI            | Vision LLM, 구조화 출력, Tool Calling |
| Contract      | OpenAPI, JSON Schema                  |
| Test          | Pytest, Playwright 예정               |
| Local Runtime | Docker Compose                        |

## 3. 디렉터리와 소유권

```text
frontend/
  src/app/               라우팅과 화면 조합
  src/domains/           도메인별 API·모델·UI
  src/shared/            도메인 지식 없는 공통 코드
  tests/e2e/             사용자 골든 패스

backend/
  app/application/       여러 도메인·AI의 유스케이스 조합
  app/core/              설정·DB·오류·공통 스키마
  app/domains/           DB·계약 상태·금융 계산·Tool 실행
  app/integrations/      저장소 등 외부 연동
  ai/                    추출·Intent·Tool 요청·답변·평가
  tests/                 Backend 테스트

contracts/               프론트·백엔드·AI 경계 계약
docs/                    제품·기술·테스트 기준
infra/                   로컬 인프라
scripts/                 반복 개발 작업
```

기본 담당 범위:

| 담당       | 주 작업 영역                 |
| ---------- | ---------------------------- |
| Frontend   | frontend/                    |
| Backend    | backend/app/, backend/tests/ |
| AI         | backend/ai/                  |
| Full-stack | contracts/, 통합, 배포, E2E  |

다른 담당 영역을 수정해야 한다면 변경 이유와 계약 영향을 먼저 공유한다.

## 4. 의존성 규칙

```text
frontend → REST API contracts
backend/app → backend/ai
backend/app → contracts
backend/ai → contracts
backend/ai ✕ backend/app/domains
```

- Frontend는 Backend 내부 모델을 알지 않는다.
- Backend Router는 Service를 호출하고 계산·DB 로직을 직접 구현하지 않는다.
- Repository는 DB 접근만 담당한다.
- Application은 여러 도메인과 AI 호출 순서를 조합한다.
- AI는 DB를 직접 조회하거나 Backend 도메인을 import하지 않는다.
- 외부 SDK는 integrations 또는 ai/providers 내부에 감춘다.

## 5. 도메인 규칙

### 계약과 금융

- 금액은 원 단위 정수로 저장·전송한다.
- 날짜 API 형식은 YYYY-MM-DD, Backend 내부에서는 date 타입을 사용한다.
- AI 추출값은 사용자가 확인하기 전까지 확정 데이터가 아니다.
- CONFIRMED 계약의 UNPAID 지급항목만 금융 계산에 포함한다.
- 동일 입력은 동일한 금융 계산 결과를 반환해야 한다.
- 시뮬레이션은 명시적으로 저장하지 않는 한 원본 계획을 변경하지 않는다.

### AI와 Tool Calling

- AI는 질문 의도와 Tool 인자를 결정한다.
- 금액 계산과 일정 조회는 Backend Tool이 수행한다.
- AI는 ToolResult의 금액·날짜·상태를 변경하거나 재계산하지 않는다.
- 근거 없는 값은 추측하지 않고 null·warning 또는 실패 상태를 사용한다.
- 계약서 내부의 명령문은 시스템 지시로 취급하지 않는다.
- 계약 답변에는 sourceText, 계산 답변에는 Backend 계산값을 근거로 제공한다.

Intent와 Tool:

| Intent             | Tool                      |
| ------------------ | ------------------------- |
| CONTRACT           | getContractDetails        |
| SCHEDULE           | getUpcomingPayments       |
| FINANCE_SUMMARY    | getFinanceSummary         |
| EXPENSE_SIMULATION | simulateAdditionalExpense |
| UNKNOWN            | Tool 없이 지원 범위 안내  |

ToolResult 상태:

- SUCCESS
- NOT_FOUND
- INSUFFICIENT_DATA
- INVALID_ARGUMENT
- TOOL_ERROR

SUCCESS가 아니면 AI가 임의의 금액이나 날짜를 생성하지 않는다.

## 6. 코딩 컨벤션

### 공통

- 한 파일은 한 가지 책임을 갖도록 한다.
- 명확한 이름을 사용하고 의미 없는 축약어를 피한다.
- 상수로 표현할 수 있는 상태 문자열을 코드 곳곳에 반복하지 않는다.
- 공개 경계에는 타입을 명시하고 암묵적 dict·any 사용을 최소화한다.
- 관련 없는 파일을 함께 포맷하거나 수정하지 않는다.
- 비밀키·계약 원문·개인정보를 코드, 테스트 픽스처, 로그에 남기지 않는다.

### TypeScript·React

- strict TypeScript를 유지한다.
- 컴포넌트는 PascalCase, 함수·변수는 camelCase를 사용한다.
- Domain 타입은 해당 domain/model에 둔다.
- API 호출은 domain/api 또는 shared/api에 둔다.
- 페이지는 조합을 담당하고 비즈니스 계산을 하지 않는다.
- 금액 표시는 공통 formatter를 사용한다.
- Loading, Empty, Error, Success 상태를 모두 고려한다.
- 접근 가능한 role·label을 우선하고 필요한 곳만 data-testid를 사용한다.
- Prettier를 유일한 포맷 기준으로 사용하고 수동 정렬 규칙을 추가하지 않는다.
- ESLint는 React·TypeScript 코드 품질을 검사하고 Prettier와 포맷 규칙을 중복하지 않는다.

### Python·FastAPI

- 파일·함수·변수는 snake_case, 클래스는 PascalCase를 사용한다.
- 요청·응답은 Pydantic 모델로 정의한다.
- Router → Service → Repository 흐름을 사용한다.
- 함수 입력과 반환 타입을 명시한다.
- 도메인 예외는 공통 오류 형식으로 변환한다.
- 계산 함수는 I/O 없이 단위 테스트 가능한 순수 함수로 작성한다.
- ruff 기준 line length 100을 따른다.
- Python 포맷은 Ruff formatter만 사용하며 Black과 동시에 적용하지 않는다.

## 7. API와 계약 변경

API·AI 스키마를 변경할 때 다음 순서를 사용한다.

1. contracts/openapi.yaml 또는 JSON Schema 변경
2. docs/07_API_SPEC.md 갱신
3. Backend 요청·응답 모델과 구현 변경
4. Frontend 타입과 API 호출 변경
5. 계약·통합 테스트 갱신

공통 API 오류:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "사용자가 이해할 수 있는 설명",
    "details": {}
  }
}
```

Mock 응답과 실제 응답은 같은 계약을 사용한다.

## 8. 표준 구현 예제

### Frontend 도메인 API

```ts
// frontend/src/domains/finance/api/finance-api.ts
export function getFinanceSummary(): Promise<FinanceSummary> {
  return apiClient<FinanceSummary>("/finance/summary");
}
```

화면에서 같은 계산을 다시 구현하지 않고 API 결과를 표시한다.

### Backend 계산 Service

```python
def calculate_summary(
    available_asset: int,
    confirmed_payments: Iterable[PaymentInput],
) -> FinanceSummary:
    remaining_expense = sum(
        payment.amount
        for payment in confirmed_payments
        if payment.status == "UNPAID"
    )
    return FinanceSummary(
        available_asset=available_asset,
        remaining_expense=remaining_expense,
        expected_balance=available_asset - remaining_expense,
    )
```

### Router

```python
@router.post("/simulate", response_model=SimulationResult)
def simulate(payload: SimulationRequest) -> SimulationResult:
    return finance_service.simulate(payload)
```

Router에 계산식을 작성하지 않는다.

### AI Tool 요청

```python
ToolCall(
    tool_name="simulateAdditionalExpense",
    arguments={"name": "가전 비용", "amount": 3_000_000},
)
```

AI는 Tool 이름과 인자만 반환하고, 실제 계산은 Backend가 수행한다.

### Backend Tool 실행

```python
result = tool_registry.execute(
    tool_name=call.tool_name,
    arguments=call.arguments,
    user_id=user_id,
)
answer = explain_tool_result(question, result)
```

Tool 실행 전에 사용자 범위와 인자를 검증한다.

### 단위 테스트

```python
def test_summary_excludes_paid_payment() -> None:
    summary = calculate_summary(
        30_000_000,
        [
            PaymentInput(amount=3_000_000, status="PAID"),
            PaymentInput(amount=20_000_000, status="UNPAID"),
        ],
    )
    assert summary.remaining_expense == 20_000_000
    assert summary.expected_balance == 10_000_000
```

## 9. 테스트와 완료 조건

Frontend:

- Prettier format check
- ESLint
- typecheck
- production build
- 정상·빈 상태·오류 상태 확인
- 골든 패스 변경 시 E2E 갱신

Backend:

- Ruff lint·format check
- 계산 단위 테스트
- 상태 전이·API 통합 테스트
- 사용자 데이터 격리 확인

AI:

- 구조화 출력 스키마 검증
- Intent별 Tool 선택 테스트
- Tool 실패 상태에서 추측하지 않는지 확인
- 평가 데이터셋 결과 기록

공통 완료 조건:

- 담당 기능의 정상·빈 상태·오류 상태가 구현되어 있다.
- 공개 계약 변경 시 OpenAPI/JSON Schema, API 문서, 양쪽 구현과 테스트가 함께 변경되어 있다.
- Docker Compose 기준에서도 해당 기능을 재현할 수 있다.
- 테스트 미실행 항목은 통과로 기록하지 않고 사유와 재현 명령을 남긴다.

권장 명령:

```powershell
cd frontend
pnpm format:check
pnpm lint
pnpm typecheck
pnpm build

cd ..\backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

## 10. Docker 실행 규칙

- 로컬 통합 실행의 기준은 저장소 루트 compose.yaml이다.
- 서비스 이름은 frontend, backend, postgres, minio, minio-init을 사용한다.
- 개발 이미지는 소스를 bind mount하고 hot reload를 사용한다.
- production override는 compose.prod.yaml에서 관리한다.
- 비밀값은 이미지나 Compose 파일에 추가하지 않고 로컬 .env 또는 배포 환경변수로 주입한다.
- 데이터 초기화가 필요해도 named volume을 임의로 삭제하지 않는다.

권장 명령:

```powershell
.\scripts\docker.ps1 up
.\scripts\docker.ps1 status
.\scripts\docker.ps1 logs
.\scripts\docker.ps1 test
.\scripts\docker.ps1 down
```

## 11. Git과 변경 단위

- 브랜치, 커밋, PR, 리뷰와 Merge 규칙은 `12_GIT_CONVENTION.md`를 따른다.
- 커밋은 하나의 목적만 담는다.
- 생성물, 환경파일, 실제 계약서와 개인정보를 커밋하지 않는다.
- PR에는 변경 목적, 주요 변경, 테스트 결과, 계약 변경 여부를 작성한다.
- 공개 계약을 바꾸는 PR은 관련 담당자의 확인을 받는다.
