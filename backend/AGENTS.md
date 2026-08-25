# Backend Agent Instructions

## 범위

- app/domains: DB, 계약 상태, 금융 계산, Tool 실행
- app/core: 설정, DB, 공통 오류
- app/integrations: 저장소 등 외부 시스템
- ai: 내부 AI 패키지

## 의존 방향

~~~text
app → ai
app → contracts
ai  → contracts
ai  ✕ app/domains
~~~

## 규칙

- Router → Service → Repository 경계를 지킵니다.
- CONFIRMED 계약의 UNPAID 지급항목만 금융 계산에 사용합니다.
- 금액은 원 단위 정수, 날짜는 date 타입을 사용합니다.
- Chat orchestration은 Tool 요청을 검증한 후 Tool Registry로 실행합니다.
- AI가 반환한 금액을 신뢰하지 않고 Backend ToolResult만 최종 계산 근거로 사용합니다.

## 완료

- 계산 단위 테스트
- 상태 전이·API 통합 테스트
- 다른 사용자 데이터 격리 확인

