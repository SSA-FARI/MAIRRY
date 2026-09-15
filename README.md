# MAIRRY

> 계약서부터 잔금까지, 우리 결혼의 AI 자금 플래너

MAIRRY는 예비부부의 결혼 계약서에서 금액·지급일·주요 조건을 추출하고, 사용자가 확정한 데이터를 기준으로 남은 지출과 예상 잔액을 관리하는 결혼 특화 금융 MVP입니다.

## 핵심 흐름

```text
계약서 업로드
→ AI 정보 추출
→ 사용자 검수·확정
→ 지급 타임라인과 예상 잔액 계산
→ 계약·금액·일정 질문
```

금액과 일정은 AI가 직접 계산하거나 추측하지 않습니다. Backend Tool이 확정 데이터로 조회·계산하고, AI는 결과를 변경하지 않고 근거와 함께 설명합니다.

## 현재 상태

현재 MVP 골든패스와 근거 기반 AI 채팅까지 연결되어 있으며, 계약 종류 확장과 답변 품질 고도화를
진행하고 있습니다.

구현된 주요 기능:

- 데모 로그인과 사용자별 활성 WeddingPlan 관리
- 결혼 예정일·가용 자금 설정 및 수정
- PDF/JPG/PNG 계약서 검증, 비공개 객체 저장소 업로드와 제한된 원문 미리보기
- AI Provider와 결정론적 Demo Fallback을 이용한 문서 분석
- 추출 결과 검수·수정·확정과 계약·지급항목·취소조건 CRUD
- 확정 계약의 미지급 항목을 기준으로 한 잔액·타임라인·추가 지출 시뮬레이션
- Backend Tool과 RAG를 결합한 근거 기반 채팅 및 대화 이력 저장
- OpenAPI·JSON Schema 검증, PostgreSQL migration, CI와 골든패스 E2E

현재 범위와 후속 과제:

- 구조화 추출 타입과 Demo Fallback은 예식장 계약 중심입니다. 촬영·드레스·메이크업 등 다양한
  결혼 계약을 공통 조항 구조로 다루는 파싱·답변 파이프라인 확장이 필요합니다.
- 로그인은 MVP용 데모 인증이며 운영용 인증·권한 체계는 후속 범위입니다.
- RAG 검색 격리, 근거 품질 평가와 지원 질문 범위를 지속적으로 보강하고 있습니다.

구현 우선순위와 완료 게이트는 `docs/10_IMPLEMENTATION_PLAN.md`, 4인 기능별 분담은
`docs/11_TEAM_OWNERSHIP.md`, Git 협업 규칙은 `docs/12_GIT_CONVENTION.md`를 기준으로 합니다.

## 프로젝트 구조

```text
MAIRRY/
├── frontend/              # Next.js UI
│   ├── src/app/
│   ├── src/domains/
│   ├── src/shared/
│   └── tests/e2e/
├── backend/               # FastAPI
│   ├── app/
│   │   ├── application/   # Backend ↔ AI orchestration
│   │   ├── core/
│   │   ├── domains/       # DB·계약·금융 계산·Tool 실행
│   │   └── integrations/
│   ├── ai/                # 추출·Agent·프롬프트·평가
│   └── tests/
├── contracts/             # OpenAPI·AI·Tool 공통 계약
├── docs/                  # 제품·설계·운영 문서
├── infra/                 # PostgreSQL·MinIO
└── scripts/               # 개발 환경 초기화
```

## 기술 스택

- Frontend: Next.js, React, TypeScript
- Backend: FastAPI, Python, PostgreSQL
- AI: Vision LLM, 구조화 출력, Tool Calling
- Storage: S3 호환 객체 스토리지
- Test: Pytest, Vitest, Playwright

## 시작하기

필수 도구:

- Docker Desktop 또는 Docker Engine + Compose v2
- production override의 !reset 지원을 위해 최신 Docker Compose 권장

Docker Compose가 운영체제와 개발 도구에 관계없는 공통 검증 환경입니다. 로컬 Python·pnpm 직접
실행은 빠른 개발을 위한 보조 경로이며, 최종 통합 결과는 Compose에서도 동일해야 합니다.

### 1. 저장소 복제

```powershell
git clone https://github.com/SSA-FARI/MAIRRY.git
cd MAIRRY
git switch develop
```

일반 기능·버그·문서 작업 브랜치는 최신 `develop`에서 생성하고 PR도 `develop`을 대상으로 합니다.
배포할 때만 `develop → main` release PR을 생성합니다. 자세한 규칙은
[docs/12_GIT_CONVENTION.md](docs/12_GIT_CONVENTION.md)를 참고합니다.

### 2. 환경파일 준비

```powershell
Copy-Item .env.example .env
```

AI 연동이 필요한 경우 .env에 실제 키와 모델명을 입력합니다. .env는 Git에 커밋하지 않습니다.

### 3. Docker로 전체 실행

```powershell
docker compose up --build -d
docker compose ps
```

접속 주소:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- MinIO API: http://localhost:9000
- MinIO Console: http://localhost:9001

로그와 종료:

```powershell
docker compose logs --follow
docker compose down
```

PowerShell 관리 스크립트를 사용할 수도 있습니다.

```powershell
.\scripts\docker.ps1 up
.\scripts\docker.ps1 migrate
.\scripts\docker.ps1 status
.\scripts\docker.ps1 logs
.\scripts\docker.ps1 test
.\scripts\docker.ps1 down
```

### 4. Docker 없이 개발 환경 준비

Python과 pnpm이 PATH에 있다면:

```powershell
.\scripts\bootstrap.ps1
```

스크립트는 프론트 의존성, Backend 가상환경·의존성, 로컬 환경파일을 준비합니다. 실제 API 키는 .env에만 입력하고 커밋하지 않습니다.

### 5. 프론트 단독 실행

```powershell
cd frontend
pnpm dev
```

기본 주소: http://localhost:3000

### 6. 백엔드 단독 실행

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

### 7. 테스트

```powershell
cd frontend
pnpm typecheck
pnpm build

cd ..\backend
.\.venv\Scripts\python.exe -m pytest

cd ..
.\scripts\validate-contracts.ps1
```

RAG migration 적용 뒤 GMS에서 발급받은 키를 `AI_API_KEY`에 설정하면 서버 시작 시 Seed Dataset을
멱등 적재합니다. 아래 명령으로 사전 검증하거나 수동 실행할 수도 있습니다.

```powershell
cd backend
python -m ai.rag.ingest_seed --dataset all --dry-run
python -m ai.rag.ingest_seed --dataset all
```

세부 구조와 운영 기준은 [docs/14_RAG_GUIDE.md](docs/14_RAG_GUIDE.md)를 참고합니다.

## 역할별 개발 범위

| 담당       | 기본 작업 범위               |
| ---------- | ---------------------------- |
| Frontend   | frontend/                    |
| Backend    | backend/app/, backend/tests/ |
| AI         | backend/ai/                  |
| Full-stack | contracts/, 통합, 배포, E2E  |

Codex와 Claude Code 모두 docs/ENGINEERING_GUIDE.md를 공통 규칙으로 사용합니다. AGENTS.md와 CLAUDE.md는 공통 문서를 연결하는 어댑터이며 규칙을 중복 관리하지 않습니다.

## 핵심 개발 원칙

- AI 추출값은 사용자 확정 전까지 금융 계산에 사용하지 않습니다.
- CONFIRMED 계약의 UNPAID 지급항목만 계산합니다.
- AI는 DB를 직접 조회하거나 금융 계산을 수행하지 않습니다.
- 일정·금액 질문은 Backend Tool을 호출합니다.
- ToolResult의 숫자·날짜·상태를 AI가 변경하지 않습니다.
- 실제 계약서, 개인정보, API 키와 환경파일을 커밋하지 않습니다.

## 문서

제품 요구사항, 구현 계획과 협업 규칙은 `docs/`에 정리되어 있습니다.

- PRD와 MVP 범위
- 사용자 흐름과 화면 명세
- 아키텍처와 ERD
- API·Agent 규칙
- 테스트 시나리오
- MVP 구현 계획과 4인 역할 분담
- Git 커밋·브랜치·PR·Merge 규칙
