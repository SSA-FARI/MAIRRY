$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    docker compose run --rm backend python -m alembic -c alembic.ini upgrade head
    docker compose run --rm backend python -m app.application.demo_seed
}
finally {
    Pop-Location
}
