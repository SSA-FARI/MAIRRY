# Scripts

반복 실행이 필요한 로컬 환경 구성, 계약 검증, 데모 데이터 생성 스크립트를 둡니다.

## Phase 0 공통 명령

```powershell
# OpenAPI, JSON Schema와 계약 예시 검증
.\scripts\validate-contracts.ps1

# Docker Compose 실행과 migration
.\scripts\docker.ps1 up
.\scripts\docker.ps1 migrate
.\scripts\docker.ps1 status
.\scripts\docker.ps1 test
.\scripts\docker.ps1 down

# Demo User의 WeddingPlan, Asset, Contract, Payment를 중복 없이 생성·갱신
.\scripts\seed-demo.ps1
```

`seed-demo.ps1`은 먼저 migration head를 적용한 뒤 설정된 `DEMO_USER_ID`의 현재 활성 계획에
재실행 가능한 Demo 데이터를 넣습니다. 기존 활성 계획이 있으면 중복 계획을 만들지 않으며,
Seed가 관리하는 계약·지급항목은 고정 UUID로 갱신합니다. 지급일과 결혼일은 실행일을 기준으로
다시 설정되어 대시보드의 다음 지급과 타임라인이 항상 확인 가능합니다.

`validate-contracts.ps1`은 기본적으로 `backend/.venv`를 사용한다. 다른 Python을 사용할 때는
`-PythonExe`를 전달한다. DB migration은 Service의 실행과 분리해 한 번만 수행한다.

## AI Provider endpoint

OpenAI 공식 API는 base URL을 비워 기본 endpoint를 사용합니다.

~~~env
AI_API_KEY=sk-...
AI_MODEL=gpt-5-mini
AI_BASE_URL=
~~~

SSAFY GMS처럼 OpenAI-compatible API를 사용할 때는 버전 경로까지 지정합니다. 마지막 슬래시는
있거나 없어도 동일하게 처리됩니다.

~~~env
AI_API_KEY=<GMS_API_KEY>
AI_MODEL=gpt-5-mini
AI_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1/
~~~
## Gemini PR 리뷰

`review-pr.mjs`는 GitHub API에서 해당 PR의 unified diff만 조회해 Gemini Interactions API로
검토하고, 고정 마커가 있는 기존 리뷰 댓글을 갱신합니다.

저장소 Settings → Secrets and variables → Actions에 `GEMINI_API_KEY` Secret을 등록해야 합니다.
Workflow는 같은 저장소의 PR에만 실행되며, Secret이 제공되지 않는 fork PR은 건너뜁니다. PR head의
변경된 스크립트가 Secret에 접근하지 못하도록 항상 base SHA의 스크립트를 checkout합니다.
