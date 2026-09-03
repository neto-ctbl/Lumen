param(
  [int]$InitialDelaySeconds = 5,
  [int]$MaxDelaySeconds = 300
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $root ".venv\Scripts\python.exe"
$delay = $InitialDelaySeconds
while ($true) {
  & $python -m agent.watcher.main
  $exitCode = $LASTEXITCODE
  if ($exitCode -eq 0) { break }
  Start-Sleep -Seconds $delay
  $delay = [Math]::Min($delay * 2, $MaxDelaySeconds)
}
