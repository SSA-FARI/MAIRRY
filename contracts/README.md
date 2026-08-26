# Shared Contracts

프론트엔드, 백엔드, AI가 공유하는 경계입니다.

- ai-extraction.schema.json: AI 문서 분석 결과
- tool-result.schema.json: 대화 Tool 공통 결과
- openapi.yaml: 외부 REST API

외부 JSON 이름은 camelCase를 사용합니다. Python 내부의 snake_case 모델은 API 또는 Provider 경계에서
alias 변환하며, 계약 파일과 구현 모델을 단순히 같은 이름으로 가정하지 않습니다.

`openapi.yaml`은 경로 목록이 아니라 request body, 정상 응답, 오류 응답, 상태 코드를 포함하는 공개
계약입니다. 변경 순서는 Engineering Guide의 계약 변경 절차를 따릅니다.

구현 내부 모델을 이 디렉터리에 두지 않습니다. 경계가 변경될 때만 수정합니다.

## 검증

```powershell
.\scripts\validate-contracts.ps1
```

검증 범위는 OpenAPI 문법, JSON Schema 문법, `contracts/examples/contract-examples.json`의 공개 API,
AI 추출 및 ToolResult 예시다. 계약을 변경할 때 예시와 검증 결과도 함께 갱신한다.
