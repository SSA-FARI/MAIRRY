# Frontend Agent Instructions

## 범위

- src/app: 라우팅과 화면 조합
- src/domains: 도메인별 API·상태·UI
- src/shared: 도메인 지식이 없는 공통 코드
- tests/e2e: 골든 패스 브라우저 테스트

## 규칙

- API 타입과 필드는 contracts/openapi.yaml을 따릅니다.
- 금액과 일정은 프론트에서 재계산하지 않습니다.
- Loading, Empty, Error, Success 상태를 구현합니다.
- 주요 사용자 행동은 접근 가능한 라벨 또는 안정적인 test id를 제공합니다.
- backend와 ai 디렉터리를 수정하지 않습니다. 계약 변경이 필요하면 먼저 contracts를 제안합니다.

## 완료

- typecheck와 build
- 변경 화면의 정상·오류 상태 확인
- 골든 패스에 영향을 주면 E2E 갱신

