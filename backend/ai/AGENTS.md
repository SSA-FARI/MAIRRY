# AI Agent Instructions

## 책임

- 계약서 구조화 추출
- 질문 Intent 분류
- Backend Tool 호출 요청 생성
- ToolResult 기반 자연어 설명
- 프롬프트·샘플·평가셋 관리

## 금지

- backend/app/domains를 import하지 않습니다.
- DB를 직접 조회하지 않습니다.
- 금액·잔액·부족액을 직접 계산하지 않습니다.
- 일정과 계약값을 추측하지 않습니다.
- ToolResult의 금액·날짜·상태를 변경하지 않습니다.

## 공개 인터페이스

- analyze_document()
- decide_tool()
- explain_tool_result()

내부 프롬프트나 provider를 backend/app에서 직접 import하지 못하게 합니다.

## 완료

- 구조화 출력 스키마 검증
- Intent별 Tool 선택 테스트
- NOT_FOUND·INSUFFICIENT_DATA·TOOL_ERROR 응답 테스트
- 평가 데이터셋 결과 기록

