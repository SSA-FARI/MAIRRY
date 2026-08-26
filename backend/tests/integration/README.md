# Integration tests

문서 상태 전이, API 계약, Chat Tool 호출과 사용자 데이터 격리를 검증합니다.

Phase 0에서는 Health API와 공통 오류 형식을 실제 FastAPI TestClient로 검증한다. DB 통합 테스트는
개발 DB와 분리된 `DATABASE_URL`을 사용하며 CI의 `mairry_test` PostgreSQL을 기준으로 한다.
