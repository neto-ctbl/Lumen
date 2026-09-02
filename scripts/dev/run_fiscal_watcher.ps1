param(
    [switch]$Once,
    [switch]$Status
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python virtualenv not found at .venv\Scripts\python.exe" }

$arguments = @("-m", "agent.watcher.main")
if ($Once) { $arguments += "--once" }
if ($Status) { $arguments += "--status" }

Set-Location $repoRoot
& $python @arguments
exit $LASTEXITCODE
