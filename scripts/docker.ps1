param(
    [ValidateSet(
        "up",
        "down",
        "rebuild",
        "logs",
        "status",
        "migrate",
        "e2e",
        "test",
        "prod-up",
        "prod-down"
    )]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

try {
    docker compose version | Out-Null

    switch ($Action) {
        "up" {
            docker compose up --build -d
            docker compose ps
        }
        "down" {
            docker compose down
        }
        "rebuild" {
            docker compose down
            docker compose build --no-cache
            docker compose up -d
            docker compose ps
        }
        "logs" {
            docker compose logs --follow --tail 200
        }
        "status" {
            docker compose ps
        }
        "migrate" {
            docker compose run --rm backend python -m alembic -c alembic.ini upgrade head
        }
        "test" {
            $runningServices = @(docker compose ps --status running --services)
            Assert-LastExitCode "Docker Compose running service lookup"
            $frontendWasRunning = $runningServices -contains "frontend"

            if ($frontendWasRunning) {
                docker compose stop frontend
                Assert-LastExitCode "Frontend development server stop"
            }

            try {
                docker compose --profile test up -d --wait postgres-test
                Assert-LastExitCode "Test database startup"

                docker compose run --rm frontend pnpm format:check
                Assert-LastExitCode "Frontend format check"
                docker compose run --rm frontend pnpm lint
                Assert-LastExitCode "Frontend lint"
                docker compose run --rm frontend pnpm typecheck
                Assert-LastExitCode "Frontend typecheck"
                docker compose run --rm frontend pnpm build
                Assert-LastExitCode "Frontend production build"
                # Docker Desktop marks bind-mounted Windows files executable. Ignore only that
                # platform metadata check; all Python syntax and quality rules remain enabled.
                docker compose run --rm backend python -m ruff check --ignore EXE002 app ai tests
                Assert-LastExitCode "Backend lint"
                docker compose run --rm backend python -m ruff format --check app ai tests
                Assert-LastExitCode "Backend format check"
                # Unit/integration tests must be deterministic and must never use a developer's
                # live AI credentials from the root .env file.
                docker compose run --rm -e AI_API_KEY= -e AI_MODEL= backend python -m pytest -p no:cacheprovider
                Assert-LastExitCode "Backend tests"
            }
            finally {
                docker compose --profile test rm --stop --force postgres-test | Out-Null
                if ($frontendWasRunning) {
                    docker compose start frontend | Out-Null
                }
            }
        }
        "e2e" {
            try {
                docker compose --profile e2e up --build -d --wait frontend-e2e
                Assert-LastExitCode "E2E application startup"
                docker compose --profile e2e run --rm --no-deps --build e2e
                Assert-LastExitCode "E2E golden path"
            }
            finally {
                docker compose --profile e2e rm --stop --force backend-e2e frontend-e2e postgres-e2e | Out-Null
            }
        }
        "prod-up" {
            docker compose -f compose.yaml -f compose.prod.yaml up --build -d
            docker compose -f compose.yaml -f compose.prod.yaml ps
        }
        "prod-down" {
            docker compose -f compose.yaml -f compose.prod.yaml down
        }
    }
}
finally {
    Pop-Location
}
