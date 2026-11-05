param([string]$StateDirectory, [string]$PythonPath)
# Interactive, explicitly user-launched sign-in. Never called by auto-start.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-common.ps1')
function Invoke-OfficialCodexLogin {
    param([string]$Executable, [string]$DedicatedHome)
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = 'login'
    $startInfo.WorkingDirectory = $DedicatedHome
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $false
    $startInfo.EnvironmentVariables.Clear()
    # Copy only routing/OS paths, never API-key or inherited agent variables.
    foreach ($name in @('SYSTEMROOT','WINDIR','SYSTEMDRIVE','PATH','PATHEXT','USERPROFILE',
        'HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA','TEMP','TMP','HOME',
        'HTTPS_PROXY','HTTP_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','SSL_CERT_DIR',
        'CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS')) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ($null -ne $value) { $startInfo.EnvironmentVariables[$name] = $value }
    }
    $startInfo.EnvironmentVariables['CODEX_HOME'] = $DedicatedHome
    $process = [Diagnostics.Process]::Start($startInfo)
    try { $process.WaitForExit(); return $process.ExitCode } finally { $process.Dispose() }
}
$statePath = Get-BridgeStateDirectory $StateDirectory
$configPath = Initialize-BridgeConfiguration $statePath
$python = Get-BridgePython $PythonPath
$resolver = @'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from bridge import Config
config = Config.load(Path(sys.argv[2]))
print(json.dumps({"executable": config.codex_path}))
'@
$resolved = $resolver | & $python -B - $PSScriptRoot $configPath
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the official Codex CLI. Install/update it, or set codex_path in config.json.' }
$executable = ($resolved | ConvertFrom-Json).executable
if (-not $executable -or -not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'Native Codex CLI not found.' }
$settings = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($settings.codex_home -ne 'isolated') {
    Write-Host 'This helper uses a dedicated Codex home for NPC conversations.'
    Write-Host 'It will preserve your other settings and back up config.json before setting codex_home to isolated.'
    if ((Read-Host 'Continue? [y/N]') -notmatch '^[yY]$') { exit 0 }
    $backupPath = Join-Path $statePath ('config.before-isolated-' + [Guid]::NewGuid().ToString('N') + '.json')
    Copy-Item -LiteralPath $configPath -Destination $backupPath -ErrorAction Stop
    $settings | Add-Member -NotePropertyName codex_home -NotePropertyValue 'isolated' -Force
    $temporaryPath = Join-Path $statePath ('config.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $settings | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $temporaryPath -Encoding utf8
        Move-Item -LiteralPath $temporaryPath -Destination $configPath -Force
    } finally { if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath } }
}
$dedicatedHome = Join-Path $statePath 'codex-home'
New-Item -ItemType Directory -Path $dedicatedHome -Force | Out-Null
foreach ($name in @('AGENTS.md', 'AGENTS.override.md')) {
    if (Test-Path -LiteralPath (Join-Path $dedicatedHome $name)) { throw 'Remove personal instructions from the dedicated home before signing in. The helper does not delete them.' }
}
$previousHome = $env:CODEX_HOME
try {
    $env:CODEX_HOME = $dedicatedHome
    Write-Host 'Signing in with your own account through the official Codex CLI. No credentials are copied from another home.'
    $result = Invoke-OfficialCodexLogin $executable $dedicatedHome
} finally { $env:CODEX_HOME = $previousHome }
exit $result
