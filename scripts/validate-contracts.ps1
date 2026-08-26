param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonExe) {
    $venvPython = Join-Path $projectRoot "backend/.venv/Scripts/python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        $PythonExe = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python을 찾을 수 없습니다. -PythonExe로 실행 파일 경로를 전달하세요."
        }
        $PythonExe = $pythonCommand.Source
    }
}

& $PythonExe (Join-Path $PSScriptRoot "validate_contracts.py")
