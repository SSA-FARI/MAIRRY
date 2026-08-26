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
```

`validate-contracts.ps1`은 기본적으로 `backend/.venv`를 사용한다. 다른 Python을 사용할 때는
`-PythonExe`를 전달한다. DB migration은 Service의 실행과 분리해 한 번만 수행한다.

## Gemini PR 리뷰

`review-pr.mjs`는 GitHub API에서 해당 PR의 unified diff만 조회해 Gemini Interactions API로
검토하고, 고정 마커가 있는 기존 리뷰 댓글을 갱신합니다.

저장소 Settings → Secrets and variables → Actions에 `GEMINI_API_KEY` Secret을 등록해야 합니다.
Workflow는 같은 저장소의 PR에만 실행되며, Secret이 제공되지 않는 fork PR은 건너뜁니다. PR head의
변경된 스크립트가 Secret에 접근하지 못하도록 항상 base SHA의 스크립트를 checkout합니다.
