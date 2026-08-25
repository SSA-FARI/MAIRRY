param(
    [ValidateSet(
        "up",
        "down",
        "rebuild",
        "logs",
        "status",
        "test",
        "prod-up",
        "prod-down"
    )]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

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
        "test" {
            docker compose run --rm frontend pnpm typecheck
            docker compose run --rm backend python -m pytest
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

