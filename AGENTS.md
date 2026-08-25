# Project Agent Instructions

개발 전 docs/02_MVP_SCOPE.md와 docs/08_AGENTS.md를 읽습니다.

## 작업 경계

- 프론트 기능은 frontend/src/domains 안에서 도메인별로 구현합니다.
- 백엔드 기능은 backend/app/domains 안에서 도메인별로 구현합니다.
- AI 프롬프트·추출·Agent·평가는 backend/ai에서 구현합니다.
- 외부 모델·스토리지 SDK는 integrations 또는 AI provider 밖으로 노출하지 않습니다.
- 공통 API·AI 스키마는 contracts에서 관리합니다.
- 금액은 원 단위 정수, 날짜는 YYYY-MM-DD 형식을 사용합니다.
- CONFIRMED 계약의 UNPAID 지급항목만 금융 계산에 포함합니다.
- AI가 금액·일정을 직접 계산하거나 Tool 결과를 변경하지 못하게 합니다.
- AI는 backend 도메인을 import하지 않고 Tool 요청만 반환합니다.
- backend는 AI의 공개 인터페이스만 호출합니다.

## 완료 조건

- 변경 영역의 테스트를 실행합니다.
- API 변경 시 contracts와 docs/07_API_SPEC.md를 갱신합니다.
- 핵심 흐름 변경 시 docs/09_TEST_SCENARIO.md를 갱신합니다.
