# 13. Phase 0 공통 결정

## 목적

Phase 1 병렬 개발 전에 A/B/C/D가 공유해야 하는 데이터 타입과 실행 정책을 고정한다. 공개 계약과
충돌하면 `contracts/`와 `docs/07_API_SPEC.md`를 우선 갱신한다.

## 데이터 타입

| 항목 | 결정 |
|---|---|
| ID | UUID v4, API에서는 string |
| 금액 | 원 단위 정수, DB BIGINT, 0과 null을 구분 |
| 날짜 | API `YYYY-MM-DD`, Python `date`, DB DATE |
| 시각 | timezone 포함 ISO 8601, DB UTC TIMESTAMPTZ |
| JSON 필드 | 외부 camelCase, Python 내부 snake_case |
| 빈 목록 | `[]`; 목록 전체를 null로 보내지 않음 |
| 사용자 | 서버 설정 `DEMO_USER_ID`; 요청에서 userId를 받지 않음 |
| 추가 필드 | 공개 요청과 AI 구조화 출력에서 거부 |

상태값은 `contracts/openapi.yaml`, `ai-extraction.schema.json`, `tool-result.schema.json`의 Enum을
사용한다. 구현에서 임의 상태 문자열을 추가하지 않는다.

## 계약과 금융

- Payment amount가 null인 추출값은 확정할 수 있지만 금융 계산에서 제외하고 확인 필요로 표시한다.
- Payment가 없는 계약도 확정할 수 있다.
- Payment 합계와 totalPrice가 달라도 확정을 막지 않고 warning으로 안내한다.
- CONFIRMED 계약의 amount가 있는 UNPAID Payment만 남은 지출에 포함한다.
- 과거 UNPAID 항목도 남은 지출에는 포함한다.
- nearestPayment는 기준일 이후 dueDate가 있는 가장 이른 UNPAID 항목이다.
- 시뮬레이션은 저장하지 않으며 원본 계획과 Payment를 변경하지 않는다.
- 확정 계약 수정·삭제와 Payment 상태 변경 API는 MVP 공개 범위에서 제외한다.

## 문서와 분석

- 지원 형식은 PDF, JPEG, PNG이며 기본 최대 크기는 10 MiB로 한다.
- PDF 최대 페이지는 20페이지로 제한한다.
- 확장자와 MIME을 모두 확인한다.
- Provider timeout은 45초, Frontend 폴링은 1초, UI timeout은 60초다.
- 자동 재시도는 하지 않으며 FAILED 문서는 사용자가 재시도할 수 있다.
- 오래된 PROCESSING 복구는 Phase 1 Document Service에서 실패 상태 전환 정책으로 구현한다.
- 원문은 공개 URL로 제공하지 않고 5분 유효 Presigned URL을 사용한다.

## DB와 트랜잭션

- Service가 commit/rollback을 포함한 트랜잭션 경계를 소유한다.
- Repository는 DB 접근만 담당하고 임의로 commit하지 않는다.
- 기능별 모델과 migration은 기능 담당자가 작성하고 D가 migration head와 공통 규칙을 검토한다.
- 테스트는 개발 DB와 분리된 `TEST_DATABASE_URL` 또는 CI PostgreSQL을 사용한다.

## 리뷰

- A: WeddingPlan, Payment, Finance 계산 규칙
- B: Document, 파일 제한, 분석 상태 전이
- C: Contract, Chat, ToolResult
- D: OpenAPI, JSON Schema, migration, Compose, CI 검증

Phase 1 시작 전 A/B/C 리뷰에서 변경된 결정은 관련 계약과 테스트 예시에 함께 반영한다.
