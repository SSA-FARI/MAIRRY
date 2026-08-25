param(
    [string]$PythonExe = "",
    [string]$PnpmExe = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $pythonCommand) {
        throw "Python을 찾을 수 없습니다. -PythonExe로 실행 파일 경로를 전달하세요."
    }
    $PythonExe = $pythonCommand.Source
}

if (-not $PnpmExe) {
    $pnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
    if (-not $pnpmCommand) {
        throw "pnpm을 찾을 수 없습니다. -PnpmExe로 실행 파일 경로를 전달하세요."
    }
    $PnpmExe = $pnpmCommand.Source
}

Write-Host "1/3 Installing frontend dependencies"
Push-Location (Join-Path $projectRoot "frontend")
& $PnpmExe install
Pop-Location

Write-Host "2/3 Creating backend virtual environment"
Push-Location (Join-Path $projectRoot "backend")
& $PythonExe -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
Pop-Location

Write-Host "3/3 Copying environment template"
$envTarget = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $envTarget)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot ".env.example") -Destination $envTarget
}

Write-Host "Bootstrap complete. Configure .env before running external AI or storage."
