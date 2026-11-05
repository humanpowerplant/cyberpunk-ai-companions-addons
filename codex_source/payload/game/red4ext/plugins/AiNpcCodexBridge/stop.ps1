param([string]$StateDirectory)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-common.ps1')
$statePath = Get-BridgeStateDirectory $StateDirectory
$pidPath = Join-Path $statePath 'server.pid.json'
if (-not (Test-Path -LiteralPath $pidPath)) { @{ status = 'no-owned-pid-record' } | ConvertTo-Json; exit 0 }
$record = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
$process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
if (-not $process) { Remove-Item -LiteralPath $pidPath; @{ status = 'already-stopped' } | ConvertTo-Json; exit 0 }
if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$record.start_ticks -or $process.Path -ne $record.executable) {
    throw 'PID identity changed. This PID record no longer identifies the bridge process.'
}
$expectedScript = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'bridge.py')).Path
if ([IO.Path]::GetFullPath($record.script) -ne $expectedScript -or $record.url -notmatch '^http://127\.0\.0\.1:\d+$') {
    throw 'PID record does not belong to this installation.'
}
try {
    $health = Invoke-RestMethod -Uri ($record.url + '/healthz') -MaximumRedirection 0 -TimeoutSec 2
    if ($health.service -eq 'codex-companion-bridge' -and $health.local_auth -eq 'bearer-v1') {
        $headers = Get-BridgeVerifiedHeaders $statePath $record.url
        Invoke-RestMethod -Uri ($record.url + '/shutdown') -Headers $headers -Method Post -MaximumRedirection 0 -TimeoutSec 3 | Out-Null
    }
} catch {}
try { Wait-Process -Id ([int]$record.pid) -Timeout 25 -ErrorAction Stop } catch {
    $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq [long]$record.start_ticks -and $process.Path -eq $record.executable) {
        $taskkill = Join-Path $env:SystemRoot 'System32/taskkill.exe'
        $kill = Start-Process -FilePath $taskkill -ArgumentList @('/PID', [string]$record.pid, '/T', '/F') -WindowStyle Hidden -Wait -PassThru
        if ($kill.ExitCode -ne 0) { throw 'The owned bridge process could not be stopped.' }
    }
}
Remove-Item -LiteralPath $pidPath
@{ status = 'stopped'; pid = $record.pid } | ConvertTo-Json
