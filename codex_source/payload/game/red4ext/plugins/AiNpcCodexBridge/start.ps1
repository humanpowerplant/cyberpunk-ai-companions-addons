param([string]$StateDirectory, [string]$PythonPath, [ValidateRange(0,2147483647)][int]$ParentProcessId = 0)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-common.ps1')
$statePath = Get-BridgeStateDirectory $StateDirectory
$configPath = Initialize-BridgeConfiguration $statePath
$bridgeUrl = Get-BridgeUrl $configPath
$pidPath = Join-Path $statePath 'server.pid.json'
function Test-CompatibleBridgeHealth {
    param($Health)
    return $Health -and $Health.status -eq 'ok' -and $Health.service -eq 'codex-companion-bridge' -and
        $Health.version -eq 1 -and $Health.auth_mode -eq 'chatgpt'
}
$status = $null
try { $status = Invoke-RestMethod -Uri ($bridgeUrl + '/healthz') -MaximumRedirection 0 -TimeoutSec 2 } catch {}
if ($status) {
    if (-not (Test-CompatibleBridgeHealth $status)) {
        throw 'A different or incompatible service owns the configured port.'
    }
    if ($status.local_auth -ne 'bearer-v1') {
        throw 'An older unauthenticated Codex bridge is running. Stop that bridge yourself, then restart with the updated files. It has not been adopted or stopped.'
    }
    $headers = Get-BridgeVerifiedHeaders $statePath $bridgeUrl
    try {
        $selection = Invoke-RestMethod -Uri ($bridgeUrl + '/codex/settings') -Headers $headers -MaximumRedirection 0 -TimeoutSec 2
        if ($selection.status -ne 'ok') { throw 'Unexpected selection response.' }
    } catch { throw 'The running bridge does not accept this user state credential. It has not been adopted or stopped.' }
    # Readiness may be borrowed from a compatible manually started bridge. This
    # does not adopt it: do not create/replace a PID record, attach a parent or stop it.
    $status | ConvertTo-Json -Depth 5
    exit 0
}
$python = Get-BridgePython $PythonPath
$script = Join-Path $PSScriptRoot 'bridge.py'
$arguments = @('-B', '-u', ('"' + $script + '"'), '--config', ('"' + $configPath + '"'), '--data-dir', ('"' + $statePath + '"'))
if ($ParentProcessId -gt 0) { $arguments += @('--parent-pid', [string]$ParentProcessId) }
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $statePath -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $statePath 'server.status.log') -RedirectStandardError (Join-Path $statePath 'server.errors.log')
$process.Refresh()
@{ pid = $process.Id; start_ticks = $process.StartTime.ToUniversalTime().Ticks; executable = $process.Path; script = $script; url = $bridgeUrl } |
    ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding utf8
$readyDeadline = [DateTime]::UtcNow.AddSeconds(15)
while ([DateTime]::UtcNow -lt $readyDeadline) {
    Start-Sleep -Milliseconds 500
    $process.Refresh()
    if ($process.HasExited) { throw 'Bridge startup failed. Inspect server.status.log in the bridge state directory.' }
    try {
        $status = Invoke-RestMethod -Uri ($bridgeUrl + '/healthz') -MaximumRedirection 0 -TimeoutSec 1
        if ((Test-CompatibleBridgeHealth $status) -and $status.local_auth -eq 'bearer-v1') {
            $headers = Get-BridgeVerifiedHeaders $statePath $bridgeUrl
            $selection = Invoke-RestMethod -Uri ($bridgeUrl + '/codex/settings') -Headers $headers -MaximumRedirection 0 -TimeoutSec 1
            if ($selection.status -ne 'ok') { continue }
            $status | ConvertTo-Json -Depth 5
            exit 0
        }
    } catch {}
}
throw 'Bridge readiness timed out. Run stop.ps1 to stop the owned process.'
