param(
    [ValidateSet("Start", "Stop", "Status")]
    [string]$Action = "Start",
    [string]$OrganizationSlug = "neto-contabilidade",
    [string]$Directory = "scripts/collectors/dominio/Relatorios_Dominio",
    [ValidateRange(10, 3600)]
    [int]$IntervalSeconds = 60,
    [switch]$Foreground,
    [switch]$DryRun
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$watcher = Join-Path $repoRoot "backend\scripts\watch_dominio_payroll.py"
$canonicalDirectory = (Resolve-Path (Join-Path $repoRoot $Directory)).ProviderPath
$runtimeDirectory = Join-Path $repoRoot ".runtime\watchers"
$keyBytes = [Text.Encoding]::UTF8.GetBytes("$OrganizationSlug`n$canonicalDirectory")
$key = ([Security.Cryptography.SHA256]::Create().ComputeHash($keyBytes) | ForEach-Object ToString x2) -join ""
$lockPath = Join-Path $runtimeDirectory "dominio-payroll-$key.json"

if (-not (Test-Path $python)) { throw "Python virtualenv not found at .venv\Scripts\python.exe" }
if (-not (Test-Path $watcher)) { throw "Domínio watcher script was not found." }

function Get-OwnedWatcher {
    if (-not (Test-Path $lockPath)) { return $null }
    try { $lock = Get-Content -LiteralPath $lockPath -Raw | ConvertFrom-Json } catch { Remove-Item -LiteralPath $lockPath -Force; return $null }
    if ($lock.organization_slug -ne $OrganizationSlug -or $lock.canonical_directory -ne $canonicalDirectory) { Remove-Item -LiteralPath $lockPath -Force; return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($lock.pid)" -ErrorAction SilentlyContinue
    $valid = $process -and $process.CommandLine -match [regex]::Escape("watch_dominio_payroll.py") -and $process.CommandLine -match [regex]::Escape("--organization-slug $OrganizationSlug") -and $process.CommandLine -match [regex]::Escape($canonicalDirectory)
    if (-not $valid) { Remove-Item -LiteralPath $lockPath -Force; return $null }
    return [PSCustomObject]@{ Lock = $lock; Process = $process }
}

function Get-UnmanagedWatchers {
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match [regex]::Escape("watch_dominio_payroll.py") -and $_.CommandLine -match [regex]::Escape("--organization-slug $OrganizationSlug")
    }
}

function Get-ManagedProcessIds {
    param([int]$RootPid)

    $ids = @($RootPid)
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue($RootPid)
    while ($pending.Count -gt 0) {
        $parentPid = $pending.Dequeue()
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$parentPid" -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            $childPid = [int]$child.ProcessId
            if ($ids -notcontains $childPid) {
                $ids += $childPid
                $pending.Enqueue($childPid)
            }
        }
    }
    return $ids
}

$owned = Get-OwnedWatcher
if ($Action -eq "Status") {
    if ($owned) {
        $ownedPid = [int]$owned.Process.ProcessId
        $managedPids = @(Get-ManagedProcessIds -RootPid $ownedPid)
        $unmanaged = @(Get-UnmanagedWatchers | Where-Object { [int]$_.ProcessId -notin $managedPids })
        [PSCustomObject]@{ running = $true; pid = $owned.Process.ProcessId; organization = $OrganizationSlug; directory = $canonicalDirectory; managed = $true; unmanaged_process_detected = ($unmanaged.Count -gt 0) }
    }
    else { [PSCustomObject]@{ running = $false; pid = $null; organization = $OrganizationSlug; directory = $canonicalDirectory; managed = $false; unmanaged_process_detected = (@(Get-UnmanagedWatchers).Count -gt 0) } }
    return
}
if ($Action -eq "Stop") {
    if (-not $owned) { Write-Output "stopped=0 already_stopped=true"; return }
    $managedPids = @(Get-ManagedProcessIds -RootPid ([int]$owned.Process.ProcessId))
    $managedPids | Sort-Object -Descending | ForEach-Object { Stop-Process -Id $_ -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    Write-Output "stopped=1 process_id=$($owned.Process.ProcessId)"
    return
}
if ($owned) { Write-Output "started=false already_running=true process_id=$($owned.Process.ProcessId)"; return }
$unmanaged = @(Get-UnmanagedWatchers)
if ($unmanaged.Count -gt 0) { throw "A watcher for this organization and directory is already running outside this wrapper." }

$arguments = @(".\backend\scripts\watch_dominio_payroll.py", "--organization-slug", $OrganizationSlug, "--directory", $canonicalDirectory, "--watch", "--interval-seconds", $IntervalSeconds, "--json")
if ($DryRun) { $arguments += "--dry-run" }
if ($Foreground) { Set-Location $repoRoot; & $python @arguments; return }

New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
if (Test-Path $lockPath) { $null = Get-OwnedWatcher }
if (Test-Path $lockPath) { throw "Watcher lock could not be recovered safely." }
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru
[PSCustomObject]@{ pid = $process.Id; organization_slug = $OrganizationSlug; canonical_directory = $canonicalDirectory; started_at = (Get-Date).ToUniversalTime().ToString("o") } | ConvertTo-Json -Compress | Set-Content -LiteralPath $lockPath -NoNewline -Encoding utf8
Write-Output "started=true process_id=$($process.Id)"
