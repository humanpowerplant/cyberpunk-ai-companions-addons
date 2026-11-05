param([string]$StateDirectory)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-common.ps1')
$statePath = Get-BridgeStateDirectory $StateDirectory
try {
    $bridgeUrl = Get-BridgeUrl (Join-Path $statePath 'config.json')
    $status = Invoke-RestMethod -Uri ($bridgeUrl + '/healthz') -MaximumRedirection 0 -TimeoutSec 3
    if ($status.service -ne 'codex-companion-bridge') { throw 'Unexpected service' }
    $status | ConvertTo-Json -Depth 5
} catch {
    @{ status = 'not-running' } | ConvertTo-Json
    exit 1
}
