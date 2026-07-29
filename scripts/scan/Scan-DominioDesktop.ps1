<#
.SYNOPSIS
  Scanner local e não invasivo para mapear o aplicativo Domínio no Windows.

.DESCRIPTION
  Registra:
  - processos candidatos e processos filhos;
  - janelas abertas;
  - árvore de controles via Microsoft UI Automation;
  - controles focados;
  - elementos clicados com propriedades como AutomationId, Name, ClassName e ControlType;
  - conexões TCP/UDP dos processos monitorados;
  - opcionalmente um trace ETL do Windows;
  - opcionalmente inicia mitmproxy e configura o proxy WinINET do usuário.

  O script NÃO instala certificados, NÃO contorna certificate pinning, NÃO lê campos
  de senha por ValuePattern e NÃO altera o aplicativo Domínio.

.NOTES
  Recomendado: PowerShell 5.1 ou PowerShell 7 no Windows.
#>

[CmdletBinding()]
param(
    [ValidateRange(1, 1440)]
    [int]$DurationMinutes = 15,

    [ValidateRange(1, 60)]
    [int]$SnapshotIntervalSeconds = 3,

    [ValidateRange(100, 20000)]
    [int]$MaxControlsPerWindow = 5000,

    [string]$ProcessNamePattern = 'dominio|thomson|contabil|desktop',

    [string]$WindowTitlePattern = 'Dom[ií]nio|Thomson Reuters',

    [string]$OutputRoot = '.\scan_logs',

    [switch]$IncludeCommandLine,

    [switch]$StartNetshTrace,

    [switch]$EnableMitmProxy,

    [switch]$ConfigureWinInetProxy,

    [ValidateRange(1024, 65535)]
    [int]$ProxyPort = 8877
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class LumenUser32
{
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT point);

    [DllImport("user32.dll")]
    public static extern short GetAsyncKeyState(int virtualKey);
}

public static class LumenWinInet
{
    [DllImport("wininet.dll", SetLastError = true)]
    public static extern bool InternetSetOption(
        IntPtr hInternet,
        int dwOption,
        IntPtr lpBuffer,
        int dwBufferLength
    );

    public static void NotifyProxyChanged()
    {
        const int INTERNET_OPTION_SETTINGS_CHANGED = 39;
        const int INTERNET_OPTION_REFRESH = 37;
        InternetSetOption(IntPtr.Zero, INTERNET_OPTION_SETTINGS_CHANGED, IntPtr.Zero, 0);
        InternetSetOption(IntPtr.Zero, INTERNET_OPTION_REFRESH, IntPtr.Zero, 0);
    }
}
"@

function Get-IsoTimestamp {
    return [DateTimeOffset]::Now.ToString('o')
}

function Write-JsonLine {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] $Value
    )

    $json = $Value | ConvertTo-Json -Depth 12 -Compress
    Add-Content -LiteralPath $Path -Value $json -Encoding utf8
}

function Get-Sha256String {
    param([Parameter(Mandatory)][string]$Value)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Protect-CommandLine {
    param([AllowNull()][string]$CommandLine)

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return $null
    }

    $result = $CommandLine
    $patterns = @(
        '(?i)(password|passwd|pwd)\s*[=:]\s*("[^"]*"|''[^'']*''|\S+)',
        '(?i)(token|access_token|refresh_token|api[_-]?key)\s*[=:]\s*("[^"]*"|''[^'']*''|\S+)',
        '(?i)(authorization)\s*[=:]\s*("[^"]*"|''[^'']*''|\S+)'
    )

    foreach ($pattern in $patterns) {
        $result = [regex]::Replace($result, $pattern, '$1=<REDACTED>')
    }

    return $result
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-AutomationElementRecord {
    param(
        [Parameter(Mandatory)]
        [System.Windows.Automation.AutomationElement]$Element
    )

    try {
        $rect = $Element.Current.BoundingRectangle
        $controlType = $Element.Current.ControlType
        $controlTypeName = if ($null -ne $controlType) {
            $controlType.ProgrammaticName
        }
        else {
            $null
        }

        return [ordered]@{
            timestamp              = Get-IsoTimestamp
            process_id             = $Element.Current.ProcessId
            native_window_handle   = $Element.Current.NativeWindowHandle
            name                   = $Element.Current.Name
            automation_id          = $Element.Current.AutomationId
            class_name             = $Element.Current.ClassName
            framework_id           = $Element.Current.FrameworkId
            control_type           = $controlTypeName
            localized_control_type = $Element.Current.LocalizedControlType
            is_enabled             = $Element.Current.IsEnabled
            is_offscreen           = $Element.Current.IsOffscreen
            has_keyboard_focus     = $Element.Current.HasKeyboardFocus
            is_keyboard_focusable  = $Element.Current.IsKeyboardFocusable
            bounding_rectangle     = [ordered]@{
                x      = [math]::Round($rect.X, 2)
                y      = [math]::Round($rect.Y, 2)
                width  = [math]::Round($rect.Width, 2)
                height = [math]::Round($rect.Height, 2)
            }
        }
    }
    catch {
        return [ordered]@{
            timestamp = Get-IsoTimestamp
            error     = $_.Exception.Message
        }
    }
}

function Get-TopLevelWindows {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $collection = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Children,
        [System.Windows.Automation.Condition]::TrueCondition
    )

    $result = @()
    foreach ($window in $collection) {
        try {
            $result += [pscustomobject]@{
                Element   = $window
                ProcessId = $window.Current.ProcessId
                Name      = $window.Current.Name
                ClassName = $window.Current.ClassName
                Handle    = $window.Current.NativeWindowHandle
            }
        }
        catch {
            continue
        }
    }

    return $result
}

function Get-SeedProcessIds {
    param([object[]]$TopLevelWindows)

    $ids = [System.Collections.Generic.HashSet[int]]::new()

    foreach ($proc in (Get-CimInstance Win32_Process)) {
        $haystack = @(
            $proc.Name,
            $proc.ExecutablePath,
            $proc.Description
        ) -join ' '

        if ($haystack -match $ProcessNamePattern) {
            [void]$ids.Add([int]$proc.ProcessId)
        }
    }

    foreach ($window in $TopLevelWindows) {
        if (
            ($window.Name -match $WindowTitlePattern) -or
            ($window.Name -match $ProcessNamePattern) -or
            ($window.ClassName -match $ProcessNamePattern)
        ) {
            [void]$ids.Add([int]$window.ProcessId)
        }
    }

    return @($ids)
}

function Expand-ProcessTree {
    param(
        [Parameter(Mandatory)]
        [int[]]$SeedProcessIds
    )

    $all = @(Get-CimInstance Win32_Process)
    $selected = [System.Collections.Generic.HashSet[int]]::new()

    foreach ($id in $SeedProcessIds) {
        [void]$selected.Add($id)
    }

    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($proc in $all) {
            if ($selected.Contains([int]$proc.ParentProcessId) -and -not $selected.Contains([int]$proc.ProcessId)) {
                [void]$selected.Add([int]$proc.ProcessId)
                $changed = $true
            }
        }
    }

    return @($selected)
}

function Get-ProcessRecords {
    param([Parameter(Mandatory)][int[]]$ProcessIds)

    $records = @()
    $all = @(Get-CimInstance Win32_Process)

    foreach ($proc in $all | Where-Object { $ProcessIds -contains [int]$_.ProcessId }) {
        $versionInfo = $null
        if (-not [string]::IsNullOrWhiteSpace($proc.ExecutablePath) -and (Test-Path -LiteralPath $proc.ExecutablePath)) {
            try {
                $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($proc.ExecutablePath)
            }
            catch {
                $versionInfo = $null
            }
        }

        $record = [ordered]@{
            timestamp          = Get-IsoTimestamp
            process_id         = [int]$proc.ProcessId
            parent_process_id  = [int]$proc.ParentProcessId
            name               = $proc.Name
            executable_path    = $proc.ExecutablePath
            description        = $proc.Description
            creation_date      = $proc.CreationDate
            product_name       = if ($null -ne $versionInfo) { $versionInfo.ProductName } else { $null }
            product_version    = if ($null -ne $versionInfo) { $versionInfo.ProductVersion } else { $null }
            file_version       = if ($null -ne $versionInfo) { $versionInfo.FileVersion } else { $null }
        }

        if ($IncludeCommandLine) {
            $record.command_line = Protect-CommandLine $proc.CommandLine
        }

        $records += [pscustomobject]$record
    }

    return $records
}

function Get-NetworkRecords {
    param([Parameter(Mandatory)][int[]]$ProcessIds)

    $records = @()

    foreach ($pidValue in $ProcessIds) {
        try {
            foreach ($conn in @(Get-NetTCPConnection -OwningProcess $pidValue -ErrorAction Stop)) {
                $records += [pscustomobject][ordered]@{
                    protocol       = 'TCP'
                    process_id     = $pidValue
                    local_address  = $conn.LocalAddress
                    local_port     = $conn.LocalPort
                    remote_address = $conn.RemoteAddress
                    remote_port    = $conn.RemotePort
                    state          = [string]$conn.State
                }
            }
        }
        catch {
            # Processo pode encerrar entre a descoberta e a consulta.
        }

        try {
            foreach ($udp in @(Get-NetUDPEndpoint -OwningProcess $pidValue -ErrorAction Stop)) {
                $records += [pscustomobject][ordered]@{
                    protocol       = 'UDP'
                    process_id     = $pidValue
                    local_address  = $udp.LocalAddress
                    local_port     = $udp.LocalPort
                    remote_address = $null
                    remote_port    = $null
                    state          = $null
                }
            }
        }
        catch {
        }
    }

    return $records | Sort-Object protocol, process_id, local_address, local_port, remote_address, remote_port -Unique
}

function Get-UiSnapshot {
    param(
        [Parameter(Mandatory)]
        [System.Windows.Automation.AutomationElement]$WindowElement,

        [Parameter(Mandatory)]
        [int]$MaxControls
    )

    $windowRecord = Get-AutomationElementRecord -Element $WindowElement
    $controls = @()

    try {
        $collection = $WindowElement.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition
        )

        $count = [Math]::Min($collection.Count, $MaxControls)
        for ($index = 0; $index -lt $count; $index++) {
            $controls += Get-AutomationElementRecord -Element $collection.Item($index)
        }

        return [ordered]@{
            timestamp      = Get-IsoTimestamp
            truncated      = ($collection.Count -gt $MaxControls)
            total_detected = $collection.Count
            window         = $windowRecord
            controls       = $controls
        }
    }
    catch {
        return [ordered]@{
            timestamp = Get-IsoTimestamp
            window    = $windowRecord
            error     = $_.Exception.Message
            controls  = @()
        }
    }
}

function Get-ClickedElement {
    $point = New-Object LumenUser32+POINT
    [void][LumenUser32]::GetCursorPos([ref]$point)

    try {
        $automationPoint = [System.Windows.Point]::new($point.X, $point.Y)
        $element = [System.Windows.Automation.AutomationElement]::FromPoint($automationPoint)
        if ($null -eq $element) {
            return $null
        }

        $record = Get-AutomationElementRecord -Element $element
        $record.click_x = $point.X
        $record.click_y = $point.Y
        return $record
    }
    catch {
        return [ordered]@{
            timestamp = Get-IsoTimestamp
            click_x   = $point.X
            click_y   = $point.Y
            error     = $_.Exception.Message
        }
    }
}

function Get-FocusedElementRecord {
    try {
        $element = [System.Windows.Automation.AutomationElement]::FocusedElement
        if ($null -eq $element) {
            return $null
        }
        return Get-AutomationElementRecord -Element $element
    }
    catch {
        return $null
    }
}

function Backup-WinInetProxy {
    $path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $item = Get-ItemProperty -Path $path

    return [ordered]@{
        path          = $path
        proxy_enable  = $item.ProxyEnable
        proxy_server  = $item.ProxyServer
        proxy_override = $item.ProxyOverride
    }
}

function Set-WinInetProxy {
    param(
        [Parameter(Mandatory)][int]$Port
    )

    $path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    Set-ItemProperty -Path $path -Name ProxyEnable -Type DWord -Value 1
    Set-ItemProperty -Path $path -Name ProxyServer -Type String -Value "127.0.0.1:$Port"
    Set-ItemProperty -Path $path -Name ProxyOverride -Type String -Value '<local>'
    [LumenWinInet]::NotifyProxyChanged()
}

function Restore-WinInetProxy {
    param([Parameter(Mandatory)]$Backup)

    $path = $Backup.path
    Set-ItemProperty -Path $path -Name ProxyEnable -Type DWord -Value ([int]$Backup.proxy_enable)

    if ($null -ne $Backup.proxy_server) {
        Set-ItemProperty -Path $path -Name ProxyServer -Type String -Value ([string]$Backup.proxy_server)
    }
    else {
        Remove-ItemProperty -Path $path -Name ProxyServer -ErrorAction SilentlyContinue
    }

    if ($null -ne $Backup.proxy_override) {
        Set-ItemProperty -Path $path -Name ProxyOverride -Type String -Value ([string]$Backup.proxy_override)
    }
    else {
        Remove-ItemProperty -Path $path -Name ProxyOverride -ErrorAction SilentlyContinue
    }

    [LumenWinInet]::NotifyProxyChanged()
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$scanDirectory = Join-Path $OutputRoot "dominio-$timestamp"
New-Item -ItemType Directory -Path $scanDirectory -Force | Out-Null

$paths = [ordered]@{
    manifest          = Join-Path $scanDirectory 'manifest.json'
    process_log       = Join-Path $scanDirectory 'processes.jsonl'
    windows_log       = Join-Path $scanDirectory 'windows.jsonl'
    ui_log            = Join-Path $scanDirectory 'uia_snapshots.jsonl'
    clicks_log        = Join-Path $scanDirectory 'clicks.jsonl'
    focus_log         = Join-Path $scanDirectory 'focused_controls.jsonl'
    network_log       = Join-Path $scanDirectory 'network_connections.jsonl'
    http_log          = Join-Path $scanDirectory 'http_flows_sanitized.jsonl'
    netsh_trace       = Join-Path $scanDirectory 'windows_network_trace.etl'
    console_log       = Join-Path $scanDirectory 'scanner_console.log'
}

$manifest = [ordered]@{
    started_at                    = Get-IsoTimestamp
    duration_minutes              = $DurationMinutes
    snapshot_interval_seconds     = $SnapshotIntervalSeconds
    max_controls_per_window       = $MaxControlsPerWindow
    process_name_pattern          = $ProcessNamePattern
    window_title_pattern          = $WindowTitlePattern
    include_command_line          = [bool]$IncludeCommandLine
    netsh_trace_requested         = [bool]$StartNetshTrace
    mitmproxy_requested           = [bool]$EnableMitmProxy
    configure_wininet_proxy       = [bool]$ConfigureWinInetProxy
    proxy_port                    = $ProxyPort
    output_directory              = (Resolve-Path $scanDirectory).Path
    safety = [ordered]@{
        captures_password_values    = $false
        installs_certificates       = $false
        bypasses_certificate_pinning = $false
        modifies_dominio_files      = $false
    }
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $paths.manifest -Encoding utf8

$netshStarted = $false
$mitmProcess = $null
$proxyBackup = $null

try {
    Start-Transcript -Path $paths.console_log -Force | Out-Null

    Write-Host ""
    Write-Host "Scanner Domínio iniciado." -ForegroundColor Cyan
    Write-Host "Saída: $scanDirectory"
    Write-Host "Duração: $DurationMinutes minuto(s)"
    Write-Host "Pressione Ctrl+C para encerrar antes."
    Write-Host ""

    if ($StartNetshTrace) {
        if (-not (Test-IsAdministrator)) {
            Write-Warning 'O trace ETL exige PowerShell como Administrador. O restante do scanner continuará.'
        }
        else {
            & netsh trace start capture=yes report=no correlation=yes persistent=no `
                tracefile="$($paths.netsh_trace)" maxsize=512 | Out-Host
            $netshStarted = $true
        }
    }

    if ($EnableMitmProxy) {
        $mitmCommand = Get-Command mitmdump -ErrorAction SilentlyContinue
        if ($null -eq $mitmCommand) {
            Write-Warning 'mitmdump não foi localizado no PATH. A captura HTTP opcional não será iniciada.'
        }
        else {
            $addonPath = Join-Path $PSScriptRoot 'dominio_mitm_addon.py'
            if (-not (Test-Path -LiteralPath $addonPath)) {
                Write-Warning "Addon não encontrado: $addonPath"
            }
            else {
                $env:DOMINIO_SCAN_HTTP_LOG = (Resolve-Path $scanDirectory).Path + '\http_flows_sanitized.jsonl'
                $argumentList = @(
                    '-q',
                    '-s', "`"$addonPath`"",
                    '--listen-host', '127.0.0.1',
                    '--listen-port', [string]$ProxyPort,
                    '--set', 'block_global=false'
                )

                $mitmProcess = Start-Process -FilePath $mitmCommand.Source `
                    -ArgumentList $argumentList `
                    -PassThru `
                    -WindowStyle Minimized

                Write-Host "mitmproxy iniciado em 127.0.0.1:$ProxyPort." -ForegroundColor Yellow
                Write-Warning 'O script não instala certificado. HTTPS só será descriptografado se o certificado do mitmproxy já estiver confiável e o aplicativo respeitar o proxy.'

                if ($ConfigureWinInetProxy) {
                    $proxyBackup = Backup-WinInetProxy
                    Set-WinInetProxy -Port $ProxyPort
                    Write-Host 'Proxy WinINET do usuário configurado temporariamente.' -ForegroundColor Yellow
                }
            }
        }
    }

    $endAt = [DateTimeOffset]::Now.AddMinutes($DurationMinutes)
    $lastHeavyScan = [DateTimeOffset]::MinValue
    $previousLeftButtonDown = $false
    $lastFocusSignature = $null
    $lastNetworkSignature = $null
    $lastProcessSignature = $null
    $uiHashes = @{}

    while ([DateTimeOffset]::Now -lt $endAt) {
        $leftButtonDown = (([LumenUser32]::GetAsyncKeyState(0x01) -band 0x8000) -ne 0)

        if ($leftButtonDown -and -not $previousLeftButtonDown) {
            $clicked = Get-ClickedElement
            if ($null -ne $clicked) {
                Write-JsonLine -Path $paths.clicks_log -Value $clicked
            }
        }
        $previousLeftButtonDown = $leftButtonDown

        $focused = Get-FocusedElementRecord
        if ($null -ne $focused) {
            $focusJson = $focused | ConvertTo-Json -Depth 8 -Compress
            $focusSignature = Get-Sha256String -Value $focusJson
            if ($focusSignature -ne $lastFocusSignature) {
                Write-JsonLine -Path $paths.focus_log -Value $focused
                $lastFocusSignature = $focusSignature
            }
        }

        if (([DateTimeOffset]::Now - $lastHeavyScan).TotalSeconds -ge $SnapshotIntervalSeconds) {
            $topWindows = @(Get-TopLevelWindows)
            $seedIds = @(Get-SeedProcessIds -TopLevelWindows $topWindows)

            if ($seedIds.Count -eq 0) {
                Write-Host "[$(Get-Date -Format HH:mm:ss)] Nenhum processo candidato localizado. Abra o Domínio ou ajuste os padrões." -ForegroundColor DarkYellow
            }
            else {
                $allProcessIds = @(Expand-ProcessTree -SeedProcessIds $seedIds)
                $processRecords = @(Get-ProcessRecords -ProcessIds $allProcessIds)
                $processJson = $processRecords | ConvertTo-Json -Depth 8 -Compress
                $processSignature = Get-Sha256String -Value $processJson

                if ($processSignature -ne $lastProcessSignature) {
                    Write-JsonLine -Path $paths.process_log -Value ([ordered]@{
                        timestamp = Get-IsoTimestamp
                        processes = $processRecords
                    })
                    $lastProcessSignature = $processSignature
                }

                $candidateWindows = @(
                    $topWindows | Where-Object {
                        ($allProcessIds -contains [int]$_.ProcessId) -or
                        ($_.Name -match $WindowTitlePattern)
                    }
                )

                Write-JsonLine -Path $paths.windows_log -Value ([ordered]@{
                    timestamp = Get-IsoTimestamp
                    windows   = @(
                        $candidateWindows | ForEach-Object {
                            [ordered]@{
                                process_id = $_.ProcessId
                                name       = $_.Name
                                class_name = $_.ClassName
                                handle     = $_.Handle
                            }
                        }
                    )
                })

                foreach ($window in $candidateWindows) {
                    $snapshot = Get-UiSnapshot -WindowElement $window.Element -MaxControls $MaxControlsPerWindow
                    $snapshotJson = $snapshot | ConvertTo-Json -Depth 12 -Compress
                    $snapshotHash = Get-Sha256String -Value $snapshotJson
                    $windowKey = "$($window.ProcessId):$($window.Handle)"

                    if (-not $uiHashes.ContainsKey($windowKey) -or $uiHashes[$windowKey] -ne $snapshotHash) {
                        Write-JsonLine -Path $paths.ui_log -Value $snapshot
                        $uiHashes[$windowKey] = $snapshotHash
                    }
                }

                $networkRecords = @(Get-NetworkRecords -ProcessIds $allProcessIds)
                $networkJson = $networkRecords | ConvertTo-Json -Depth 6 -Compress
                $networkSignature = Get-Sha256String -Value $networkJson

                if ($networkSignature -ne $lastNetworkSignature) {
                    Write-JsonLine -Path $paths.network_log -Value ([ordered]@{
                        timestamp   = Get-IsoTimestamp
                        connections = $networkRecords
                    })
                    $lastNetworkSignature = $networkSignature
                }

                Write-Host "[$(Get-Date -Format HH:mm:ss)] PID(s): $($allProcessIds -join ', ') | janela(s): $($candidateWindows.Count) | conexão(ões): $($networkRecords.Count)"
            }

            $lastHeavyScan = [DateTimeOffset]::Now
        }

        Start-Sleep -Milliseconds 150
    }
}
finally {
    if ($netshStarted) {
        try {
            & netsh trace stop | Out-Host
        }
        catch {
            Write-Warning "Não foi possível encerrar o netsh trace automaticamente: $($_.Exception.Message)"
        }
    }

    if ($null -ne $proxyBackup) {
        try {
            Restore-WinInetProxy -Backup $proxyBackup
            Write-Host 'Proxy WinINET restaurado.' -ForegroundColor Green
        }
        catch {
            Write-Warning "Falha ao restaurar o proxy automaticamente: $($_.Exception.Message)"
        }
    }

    if ($null -ne $mitmProcess -and -not $mitmProcess.HasExited) {
        try {
            Stop-Process -Id $mitmProcess.Id -Force
        }
        catch {
        }
    }

    try {
        Stop-Transcript | Out-Null
    }
    catch {
    }

    Write-Host ""
    Write-Host "Scanner encerrado." -ForegroundColor Green
    Write-Host "Arquivos gerados em: $scanDirectory"
    Write-Host ""
}
