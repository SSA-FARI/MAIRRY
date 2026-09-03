# 11. 4인 기능별 역할 분담

## 한눈에 보는 역할

| 담당             | 한 줄 책임                                              | 핵심 산출물                                                    | 주요 테스트            | 협업 경계                           |
| ---------------- | ------------------------------------------------------- | -------------------------------------------------------------- | ---------------------- | ----------------------------------- |
| A — 계획·금융    | 확정 계약을 실제 자금계획으로 보여준다                  | 초기 설정, 금융 API, 대시보드, 타임라인, 시뮬레이션            | PLAN, FIN              | C의 확정 Payment를 입력으로 사용    |
| B — 파일·문서    | 원본 파일을 안전하게 받고 분석 가능한 상태로 만든다     | 업로드, MinIO, Document 상태, 폴링·재시도 UI                   | DOC, 분석 상태         | D의 추출 결과를 저장하고 C에 전달   |
| C — 계약·대화    | 추출값을 확정 계약으로 만들고 근거 기반 답변을 제공한다 | 검수, 계약 확정·목록·상세, 확정 트랜잭션, Chat Tool·응답       | REVIEW, CONTRACT, CHAT | B의 Document, A의 Finance Tool 사용 |
| D — AI·통합 기반 | AI 결과와 공통 실행 기반을 안정적으로 제공한다          | Fallback, AI Provider, migration 기반, 공통 오류, Compose, E2E | AI, E2E, 보안          | 모든 기능의 계약·통합 검증          |

## 분담 원칙

- 네 명 모두 사용자에게 확인 가능한 기능 산출물을 가진다.
- 기능 담당자는 Backend·Frontend·단위/통합 테스트까지 세로로 소유한다.
- D는 모든 공통 작업을 대신 처리하는 지원 담당이 아니다. AI Provider와 Fallback의 기능 소유자다.
- DB 공통 규칙과 migration 도구는 D가 관리하지만, 기능별 모델·Repository·migration 작성은 해당 기능 담당자가 한다.
- OpenAPI와 JSON Schema는 변경을 발생시킨 담당자가 수정하고, 계약 리뷰 매트릭스의 리뷰어가 확인한다.
- 업무량은 파일 수가 아니라 외부 연동, 상태 전이, UI 수, 통합 위험을 함께 고려해 조정한다.

## 상세 책임

### 개발자 A — 계획·금융·대시보드

소유 기능:

- WeddingPlan 저장·조회 및 입력 검증
- CONFIRMED 계약의 UNPAID Payment 기반 금융 요약
- 가까운 지급일과 날짜순 타임라인
- 저장하지 않는 추가지출 시뮬레이션
- 초기 설정, 대시보드, 타임라인, 시뮬레이션 UI
- 잔액 부족·계약 없음·계획 없음 상태

주 작업 영역:

- `backend/app/domains/wedding_plan/`
- `backend/app/domains/finance/`
- `frontend/src/domains/wedding-plan/`
- `frontend/src/domains/finance/`

완료 기준: PLAN-01~~02, FIN-01~~04와 대시보드 확인 항목.

### 개발자 B — 파일·문서 분석 흐름

소유 기능:

- PDF/JPG/PNG 확장자·MIME·용량 검증
- MinIO 비공개 저장과 안전한 storage key 생성
- Document 메타데이터와 분석 상태 저장
- 분석 시작, 상태 조회, 실패 재시도
- 업로드, 분석 대기, 실패, 재시도 UI
- 원문 미리보기용 제한된 접근 방식

주 작업 영역:

- `backend/app/domains/documents/`
- `backend/app/integrations/storage/`
- `backend/app/application/document_analysis.py`
- `frontend/src/domains/documents/`

완료 기준: DOC-01~03, 분석 상태 전이 API 테스트, 객체 비공개 접근 확인.

### 개발자 C — 계약·검수·AI 대화

소유 기능:

- 추출 결과 검수·수정 UI
- Contract·Payment 확정 트랜잭션
- 확정 Contract·Payment 수정·삭제, 지급상태 간편 변경 및 Document 재검수 전환
- 계약 목록·상세와 원문 근거 표시
- Intent 결과를 Backend Tool 호출로 연결
- `getContractDetails`, `getUpcomingPayments` Tool
- A가 제공하는 Finance Tool의 Chat 연결
- ToolResult 기반 답변과 citation 구성

주 작업 영역:

- `backend/app/domains/contracts/`
- `backend/app/domains/chat/`
- `backend/app/application/chat_orchestration.py`
- `frontend/src/domains/contracts/`
- `frontend/src/domains/chat/`

완료 기준: REVIEW-01~~06, CHAT-01~~10, 계약 목록·상세 API 테스트.

### 개발자 D — AI Provider·공통 기반·통합

소유 기능:

- 해시 기반 Demo Fallback과 추출 결과 검증
- 실제 Vision AI Provider와 구조화 출력
- Intent 분류 Provider와 프롬프트 경계
- migration 도구, 공통 DB·오류·설정 기반
- OpenAPI·JSON Schema 자동 검증 기반
- Docker Compose, 반복 실행 스크립트, E2E 골든 패스
- 로그·비밀값·사용자 격리·공개 객체 접근 점검

주 작업 영역:

- `backend/ai/document_extraction/`
- `backend/ai/providers/`
- `backend/ai/prompts/`
- `backend/app/core/`
- `contracts/`, `scripts/`, `frontend/tests/e2e/`

완료 기준: AI-01~03, E2E-01, API·보안 확인과 환경 재현성.

## Backend Tool 소유권

Chat 화면은 C가 소유하지만 Tool의 결정론적 비즈니스 로직은 원천 도메인 담당자가 소유한다.

| Tool                        | 비즈니스 로직 담당 | Chat 연결 담당 |
| --------------------------- | ------------------ | -------------- |
| `getFinanceSummary`         | A                  | C              |
| `simulateAdditionalExpense` | A                  | C              |
| `getUpcomingPayments`       | C                  | C              |
| `getContractDetails`        | C                  | C              |

이 구분으로 C가 금융 계산을 중복 구현하거나 A가 Chat 표현 계층까지 수정하는 상황을 방지한다.

## 계약 리뷰 매트릭스

| 변경                         | 작성자         | 필수 리뷰어        |
| ---------------------------- | -------------- | ------------------ |
| WeddingPlan·Finance API      | A              | C, D               |
| Document 상태·업로드 API     | B              | C, D               |
| Contract·Chat·ToolResult API | C              | A, D               |
| AI Extraction Schema         | D              | B, C               |
| 기능별 DB 모델·migration     | 해당 기능 담당 | D + 영향 기능 담당 |
| Compose·환경변수·공통 오류   | D              | 영향 기능 담당     |

## 병렬 진행 순서

### 1차 — 계약과 독립 구현

- A: WeddingPlan, 금융 순수 함수, Mock 대시보드
- B: Document 모델, 업로드 검증, Storage Adapter
- C: Contract·Payment 모델, 검수 Mock UI, Tool 인터페이스
- D: migration/오류 기반, Fallback, AI Schema 검증, Compose

### 2차 — 인접 기능 연결

- A: 실제 Finance API와 대시보드 연결
- B: 업로드 → 분석 요청 → 상태 폴링 연결
- C: 검수 → 확정 → 계약 조회와 Chat Tool 연결
- D: 실제 Provider 연결과 API 계약 자동 검증

### 3차 — 골든 패스 통합

- B와 D: Document에 AI 결과 저장
- B와 C: Document 추출 결과를 Contract로 확정
- A와 C: Finance Tool 결과를 Chat 답변에 연결
- D: E2E-01, Compose 재현, 보안 확인

### 4차 — 안정화

- 각 담당자가 자신의 정상·빈 상태·오류 상태와 테스트 누락을 닫는다.
- 교차 경계 문제는 양쪽 담당자가 함께 해결하고 한쪽에 넘기지 않는다.
- Should Have는 골든 패스와 전체 테스트가 통과한 뒤에만 착수한다.

## 충돌을 줄이는 파일 소유 규칙

| 공통 파일                             | 변경 원칙                                                   |
| ------------------------------------- | ----------------------------------------------------------- |
| `contracts/openapi.yaml`              | API 변경 담당자가 수정하고 D가 형식 검증                    |
| `contracts/ai-extraction.schema.json` | D가 작성하고 B·C가 소비자 리뷰                              |
| `contracts/tool-result.schema.json`   | C가 작성하고 A·D가 리뷰                                     |
| `backend/app/main.py`                 | Router 추가 담당자가 최소 변경, D 리뷰                      |
| `compose*.yaml`, `.env.example`       | D 소유, 필요한 변수는 기능 담당자가 요청·리뷰               |
| 공통 UI·API client                    | 최초 작성자를 고정 소유자로 보지 않고 영향 담당자 리뷰 필수 |

## 브랜치 권장안

- `feat/이슈번호-plan-finance`
- `feat/이슈번호-document-flow`
- `feat/이슈번호-contract-chat`
- `feat/이슈번호-ai-integration`

공통 계약을 작은 PR로 먼저 병합하고 소비자 구현은 해당 계약을 기준으로 진행한다. 매일 최소 한 번
main을 반영하며, 골든 패스가 깨진 상태를 다음 단계로 넘기지 않는다. 상세한 Git 규칙은
`12_GIT_CONVENTION.md`를 따른다.

## 기능 완료 체크리스트

- [ ] 사용자에게 확인 가능한 Backend·Frontend 흐름이 연결됨
- [ ] 정상·빈 상태·오류 상태 구현
- [ ] 사용자 범위와 입력 검증
- [ ] API/Schema와 실제 응답 일치
- [ ] 담당 테스트 ID 자동화
- [ ] Docker Compose 기준 재현
- [ ] 로그에 비밀값·계약 원문·개인정보가 없음
- [ ] 관련 문서와 예제가 현재 코드와 일치
- [ ] 협업 경계 담당자의 리뷰 완료
