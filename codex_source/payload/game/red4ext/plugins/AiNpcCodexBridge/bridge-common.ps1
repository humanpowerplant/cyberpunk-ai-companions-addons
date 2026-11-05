function Get-BridgeStateDirectory {
    param([string]$StateDirectory)
    if ($StateDirectory) { return [IO.Path]::GetFullPath($StateDirectory) }
    return Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'AiNpcCodexBridge'
}

function Get-BridgePython {
    param([string]$PythonPath)
    if ($PythonPath) {
        $resolvedPython = (Resolve-Path -LiteralPath $PythonPath -ErrorAction Stop).Path
    } else {
        $embeddedPython = Join-Path $PSScriptRoot '../AiNpcCyberpunkMod/app/python/python.exe'
        if (Test-Path -LiteralPath $embeddedPython -PathType Leaf) {
            $resolvedPython = (Resolve-Path -LiteralPath $embeddedPython).Path
        } else {
            $resolvedPython = (Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
        }
    }
    & $resolvedPython -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or newer is required.' }
    return $resolvedPython
}

function Initialize-BridgeConfiguration {
    param([string]$StateDirectory)
    New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
    $configPath = Join-Path $StateDirectory 'config.json'
    if (-not (Test-Path -LiteralPath $configPath)) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config.example.json') -Destination $configPath
    }
    return $configPath
}

function Enter-BridgeStartupLock {
    param([string]$StateDirectory)
    # Kept as an empty file after release: deleting an unlocked pathname can
    # race a second launcher that has already acquired that same file.
    $lockPath = Join-Path $StateDirectory 'startup.lock'
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ($true) {
        try {
            return [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate,
                [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        } catch [IO.IOException] {
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Another bridge startup is still in progress. Retry after it finishes.' }
            Start-Sleep -Milliseconds 100
        }
    }
}

function Get-BridgeUrl {
    param([string]$ConfigPath)
    $bridgeSettings = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    if ($bridgeSettings.host -ne '127.0.0.1' -or $bridgeSettings.port -notmatch '^\d+$' -or
        [int]$bridgeSettings.port -lt 1024 -or [int]$bridgeSettings.port -gt 65535) {
        throw 'The bridge must use IPv4 loopback and an unprivileged port.'
    }
    return 'http://127.0.0.1:' + $bridgeSettings.port
}

function Get-BridgeHeaders {
    param([string]$StateDirectory)
    $tokenPath = Join-Path $StateDirectory 'local-token.json'
    if (-not (Test-Path -LiteralPath $tokenPath -PathType Leaf) -or (Get-Item -LiteralPath $tokenPath).Length -gt 1024) {
        throw 'Local bridge credential is unavailable. Restart the owned bridge with the updated files.'
    }
    $credential = Get-Content -LiteralPath $tokenPath -Raw | ConvertFrom-Json
    if ($credential.schema -ne 1 -or $credential.token -isnot [string] -or $credential.token -cnotmatch '^[a-f0-9]{64}$') {
        throw 'Local bridge credential is invalid. Do not share or publish the state directory.'
    }
    return @{ Authorization = 'Bearer ' + $credential.token }
}

function Get-BridgeVerifiedHeaders {
    param([string]$StateDirectory, [string]$BridgeUrl)
    if ($BridgeUrl -notmatch '^http://127\.0\.0\.1:([0-9]{4,5})$' -or [int]$Matches[1] -lt 1024 -or [int]$Matches[1] -gt 65535) { throw 'Invalid local bridge URL.' }
    $port = [int]$Matches[1]
    $headers = Get-BridgeHeaders $StateDirectory
    $random = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($random) } finally { $generator.Dispose() }
    $nonce = [BitConverter]::ToString($random).Replace('-', '').ToLowerInvariant()
    # This request discloses a fresh nonce only, never the Bearer credential.
    $health = Invoke-RestMethod -Uri ($BridgeUrl + '/healthz') -Headers @{'X-AiNpc-Challenge' = $nonce} -MaximumRedirection 0 -TimeoutSec 2
    if ($health.status -ne 'ok' -or $health.service -ne 'codex-companion-bridge' -or $health.version -ne 1 -or $health.auth_mode -ne 'chatgpt' -or $health.local_auth -ne 'bearer-v1') {
        throw 'The configured service is an old or incompatible bridge. No credential was sent.'
    }
    if ($health.local_auth_proof -isnot [string] -or $health.local_auth_proof -cnotmatch '^[a-f0-9]{64}$') { throw 'Local bridge proof rejected. No credential was sent.' }
    $hmac = New-Object Security.Cryptography.HMACSHA256
    try {
        $hmac.Key = [Text.Encoding]::ASCII.GetBytes($headers.Authorization.Substring(7))
        $data = 'AiNpcCodexBridge/bearer-v1' + "`n" + $port + "`n" + $nonce
        $expected = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($data))
    } finally { $hmac.Dispose() }
    $difference = 0
    for ($index = 0; $index -lt 32; $index++) {
        $actual = [Convert]::ToByte($health.local_auth_proof.Substring($index * 2, 2), 16)
        $difference = $difference -bor ($expected[$index] -bxor $actual)
    }
    if ($difference -ne 0) { throw 'Local bridge proof rejected. No credential was sent.' }
    return $headers
}
