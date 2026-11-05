param([string]$StateDirectory, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-common.ps1')
$statePath = Get-BridgeStateDirectory $StateDirectory
$configPath = Initialize-BridgeConfiguration $statePath
$python = Get-BridgePython $PythonPath
& $python (Join-Path $PSScriptRoot 'bridge.py') --config $configPath --data-dir $statePath --check
exit $LASTEXITCODE
