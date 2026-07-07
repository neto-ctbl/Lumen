$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$frontendPath = Join-Path $repoRoot "frontend"
$backendPort = 8011
$frontendPort = 4176

$backendPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    throw "Python virtualenv not found at .venv\Scripts\python.exe"
}

$env:INITIAL_ADMIN_EMAIL = if ($env:E2E_ADMIN_EMAIL) { $env:E2E_ADMIN_EMAIL } else { "admin@example.local" }
$env:INITIAL_ADMIN_PASSWORD = if ($env:E2E_ADMIN_PASSWORD) { $env:E2E_ADMIN_PASSWORD } else { "ChangeMe123!" }
$env:INITIAL_ADMIN_FULL_NAME = "E2E Admin"
$env:INITIAL_ORG_NAME = "Lumen"
$env:INITIAL_ORG_SLUG = "lumen"
$env:VITE_API_BASE_URL = "http://127.0.0.1:$backendPort"

$stalePids = Get-NetTCPConnection -LocalPort $backendPort, $frontendPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($stalePids) {
    Stop-Process -Id $stalePids -Force -ErrorAction SilentlyContinue
}

Set-Location $repoRoot
& $backendPython -m backend.scripts.create_initial_admin

$backendProcess = Start-Process `
    -FilePath $backendPython `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$backendPort" `
    -PassThru `
    -WindowStyle Hidden

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$backendPort/healthz" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ready) {
        throw "Backend E2E server did not become ready on http://127.0.0.1:$backendPort/healthz"
    }

    Set-Location $frontendPath
    npm run dev -- --host 127.0.0.1 --port $frontendPort
} finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force
    }
}
