# 12. Git 협업 컨벤션

## 1. Commit Convention

### 형식

```text
[type] 변경 내용
```

### Type

| Type       | 용도                              |
| ---------- | --------------------------------- |
| `init`     | 프로젝트 또는 모듈 초기 구성      |
| `feat`     | 새로운 기능 구현                  |
| `add`      | 파일, 데이터, 리소스 등 단순 추가 |
| `bug`      | 버그 수정                         |
| `refactor` | 기능 변화 없는 코드 구조 개선     |
| `docs`     | 문서 추가 및 수정                 |
| `test`     | 테스트 코드 추가 및 수정          |
| `chore`    | 의존성, 환경설정, 기타 유지보수   |
| `ci`       | CI/CD 설정 변경                   |
| `style`    | 코드 포맷 등 동작과 무관한 변경   |

### 작성 규칙

- 커밋 하나에는 하나의 목적만 담는다.
- 변경 내용을 간결하고 명확하게 작성한다.
- `수정`, `작업`, `최종` 등 범위가 불명확한 표현은 사용하지 않는다.
- 관련 없는 변경사항을 하나의 커밋에 포함하지 않는다.
- 코드 포맷 전체 적용은 기능 변경과 분리해 `[style]` 커밋으로 작성한다.

예시:

```text
[feat] 웨딩 플랜 저장 API 구현
[bug] 지급 완료 금액이 남은 지출에 포함되는 오류 수정
[docs] 문서 분석 폴링 규칙 추가
[ci] PR 최소 검증 Workflow 추가
```

## 2. Branch Convention

### 형식

```text
type/이슈번호-기능명
```

기능명은 영문 소문자와 하이픈(`-`)을 사용한다.

### Type

| Type        | 용도                         |
| ----------- | ---------------------------- |
| `feat/`     | 기능 개발                    |
| `bug/`      | 버그 수정                    |
| `refactor/` | 리팩터링                     |
| `docs/`     | 문서 작업                    |
| `test/`     | 테스트 작업                  |
| `chore/`    | 설정, 인프라, 기타 유지보수  |
| `ci/`       | CI/CD 작업                   |
| `style/`    | 코드 포맷 작업               |
| `etc/`      | 위 유형에 해당하지 않는 작업 |

작성 규칙:

- 가능하면 작업 시작 전에 Issue를 생성한다.
- Issue 번호를 Branch 이름에 포함한다.
- Branch Type은 Issue 유형과 동일하게 맞춘다.
- 브랜치 하나는 하나의 Issue 또는 하나의 명확한 작업 범위를 담당한다.

예시:

```text
feat/123-document-upload
bug/145-payment-summary
docs/152-api-contract
ci/160-gemini-review
```

## 3. Pull Request Convention

### PR 제목

Commit Convention과 동일한 Type을 사용한다.

```text
[type] 변경 내용
```

PR 제목은 개별 커밋보다 PR 전체의 변경 목적을 설명한다.

예시:

```text
[feat] 계약서 업로드와 분석 상태 조회 구현
[bug] 확정 전 계약이 금융 요약에 포함되는 오류 수정
```

### PR 본문

Repository의 `.github/PULL_REQUEST_TEMPLATE.md` 형식을 따른다.

주요 작성 항목:

- 작업 내용
- 상세 구현 내용
- 테스트 결과
- API / Schema 변경 여부
- 리뷰 포인트
- 관련 Issue

관련 Issue는 다음 형식으로 연결한다.

```text
Closes #이슈번호
```

### 작성 규칙

- PR 하나는 하나의 기능 또는 문제 해결에 집중한다.
- 관련 없는 리팩터링이나 포맷 변경을 포함하지 않는다.
- API 변경 시 OpenAPI, 관련 Schema, API 문서를 함께 수정한다.
- PR 생성 전 작성자가 Diff를 확인한다.
- 실행하지 않은 테스트를 완료했다고 표시하지 않는다.
- 미완성 작업은 Draft PR로 공유한다.

## 4. Review Convention

- 필수 리뷰어는 `11_TEAM_OWNERSHIP.md`의 계약 리뷰 매트릭스를 따른다.
- AI Code Review는 참고 자료이며 사람의 Approve를 대체하지 않는다.
- Critical과 Major 의견은 수정하거나 팀 합의 근거를 남긴 뒤 해결한다.
- Minor 의견은 현재 PR에서 수정하거나 후속 Issue로 연결한다.
- 단순 스타일은 리뷰 댓글보다 Prettier, ESLint, Ruff와 CI 결과를 따른다.
- 모든 Review Conversation을 해결한 뒤 Merge한다.

## 5. Merge Rule

`main` 브랜치는 Repository Ruleset `main-protection`으로 보호한다.

```text
Ruleset name: main-protection
Enforcement: Active

Target branches:
- Include default branch

Rules:
- Restrict deletions
- Block force pushes
- Require a pull request before merging
  - Required approvals: 1
- Require status checks to pass before merging
- Require conversation resolution before merging
```

- `main`에 직접 Push하지 않는다.
- 모든 변경사항은 Pull Request를 통해 반영한다.
- 최소 1명의 Approve가 필요하다.
- Review Conversation이 모두 해결되어야 한다.
- Required Status Check가 통과해야 한다.
- Force Push와 브랜치 삭제를 금지한다.
- Merge 방식은 Squash Merge만 허용한다.
- Merge 전 Conflict와 필수 리뷰 의견을 모두 해결한다.

Squash Merge 메시지는 PR 제목 형식인 `[type] 변경 내용`을 유지한다.
