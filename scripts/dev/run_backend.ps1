$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

$activateScript = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
}

uvicorn backend.app.main:app --reload --port 8000
