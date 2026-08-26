# 10. MVP 구현 계획

## 목적

문서에 정의된 기능을 병렬 개발하되, 계약 충돌과 통합 대기를 줄이기 위한 실행 기준이다.
기능 목록은 `02_MVP_SCOPE.md`, 공개 경계는 `contracts/`와 `07_API_SPEC.md`, 검증 기준은
`09_TEST_SCENARIO.md`를 Source of Truth로 사용한다.

## 개발 전략

- 골든 패스를 세로 슬라이스로 완성한다. 계층별 전체 구현보다 한 사용자 흐름을 먼저 연결한다.
- 외부 Vision AI보다 결정론적 Demo Fallback을 먼저 연결해 UI·DB·계산 개발을 분리한다.
- API 변경은 계약 → Backend → Frontend → 테스트 순서로 반영한다.
- DB 상태를 가진 기능은 Router → Service → Repository로 구현하고 트랜잭션 경계를 Service에 둔다.
- 실제 AI, 고급 UI, Should Have는 골든 패스 통합 이후 진행한다.

## 기준 결정

| 항목 | MVP 결정 |
|---|---|
| 실행환경 | Docker Compose가 공통 기준, 로컬 직접 실행은 보조 |
| 사용자 | `DEMO_USER_ID` 한 명, 요청으로 userId를 받지 않음 |
| 분석 방식 | `POST analyze`로 처리 시작 후 `GET document` 폴링 |
| AI 우선순위 | 해시 기반 Demo Fallback 완성 후 실제 Provider 연결 |
| 저장 | PostgreSQL + 비공개 S3 호환 객체 저장소 |
| API 명명 | 외부 JSON은 camelCase, Python 내부는 snake_case |
| 시각 | 저장은 UTC, API date-time은 timezone 포함 ISO 8601 |
| 동시 요청 | 동일 문서 분석·확정 중복은 409 |
| 삭제 | MVP 공개 API에서 제외, 운영 데이터 임의 삭제 금지 |

## 단계와 완료 게이트

### M0 — 계약과 실행 기반

- `.env.example`, Compose, bootstrap 절차가 새 환경에서 동작한다.
- OpenAPI와 JSON Schema가 문법 검증을 통과한다.
- DB migration 도구와 초기 migration을 준비한다.
- Backend 전체 테스트가 `backend/tests` 아래에서 수집된다.

완료 게이트: 빈 저장소 복제 후 문서의 명령만으로 health API와 빈 화면을 실행할 수 있다.

### M1 — 계획과 문서 수집

- WeddingPlan 저장·조회
- PDF/JPG/PNG 확장자와 MIME, 용량 검증
- 원본 파일 비공개 저장, Document 상태 저장
- 업로드·초기 설정 UI의 Loading/Empty/Error/Success

완료 게이트: PLAN-01~02, DOC-01~03 API 테스트 통과.

### M2 — 분석, 검수, 계약 확정

- Demo Fallback 분석과 추출 스키마 검증
- `UPLOADED → PROCESSING → REVIEW_REQUIRED/FAILED` 상태 전이
- 폴링, 실패 재시도, 직접 입력
- 사용자 수정값을 Contract·Payment로 원자적 저장
- 확정 전 데이터의 금융 계산 제외

완료 게이트: AI-01~03, REVIEW-01~03 통과.

### M3 — 금융 대시보드

- 확정·미지급 항목 기반 요약과 가까운 지급일
- 날짜순 타임라인과 dueDate 누락 항목 처리
- 저장하지 않는 추가지출 시뮬레이션
- 빈 상태, 부족 경고, 계약 상세 이동

완료 게이트: FIN-01~04와 대시보드 확인 항목 통과.

### M4 — 근거 기반 AI 질문

- Intent 및 인자 구조화 검증
- 네 개 Backend Tool 구현과 사용자 범위 강제
- ToolResult 실패 상태별 응답
- 계약 sourceText 또는 서버 계산값을 변경하지 않는 답변
- 실제 Provider는 Fallback 골든 패스에 영향을 주지 않게 어댑터로 연결

완료 게이트: CHAT-01~10과 AI 평가 데이터셋 통과.

### M5 — 통합과 데모 안정화

- E2E-01 자동화
- Compose에서 전체 골든 패스 실행
- 로그·객체 공개 접근·사용자 격리 확인
- 데모 체크리스트와 실제 결과 기록

완료 게이트: `09_TEST_SCENARIO.md` 데모 전 체크리스트 전부 완료.

## 상태 전이와 오류 정책

```text
UPLOADED ──analyze──> PROCESSING ──success──> REVIEW_REQUIRED ──confirm──> CONFIRMED
                           └──────failure──> FAILED ──retry────> PROCESSING
                                                └─manual confirm─> CONFIRMED
```

- PROCESSING 문서의 재분석, CONFIRMED 문서의 재확정은 409다.
- 분석 실패는 `error.message`에는 사용자용 요약만, 내부 로그에는 원문 없이 추적 ID만 남긴다.
- 확정은 Contract와 모든 Payment 저장 및 Document 상태 변경을 한 트랜잭션으로 처리한다.
- 폴링 권장 간격은 1초, 데모 타임아웃은 60초이며 타임아웃이 서버 작업을 취소하지는 않는다.

## 변경 단위

PR 하나는 가능한 한 하나의 테스트 묶음과 하나의 세로 기능을 다룬다. 공개 계약 PR은 최소한
계약 파일, API 문서, Backend 검증 테스트를 포함하고 소비자 담당자의 리뷰를 받는다.
