$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$frontendPath = Join-Path $repoRoot "frontend"
Set-Location $frontendPath

if (-not (Test-Path (Join-Path $frontendPath "node_modules"))) {
    npm install
}

npm run dev
