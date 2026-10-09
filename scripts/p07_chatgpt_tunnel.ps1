# Run in the console owning the existing tunnel after stopping its launcher.
# The API key stays in the process environment, never in arguments or receipts.
param(
    [Parameter(Mandatory=$true)][string]$TunnelId,
    [Parameter(Mandatory=$true)][string]$Bench,
    [Parameter(Mandatory=$true)][string]$Runtime,
    [string]$RestoreLauncher
)
$ErrorActionPreference = 'Stop'
if ($TunnelId -cnotmatch '^tunnel_[a-z0-9]{32}$') { throw 'Invalid tunnel ID' }
$repository = Split-Path $PSScriptRoot -Parent
$python = Join-Path $repository '.venv/Scripts/python.exe'
$script = Join-Path $PSScriptRoot 'p07_chatgpt_bench.py'
$benchPath = (Resolve-Path -LiteralPath $Bench).Path
$runtimePath = (Resolve-Path -LiteralPath $Runtime).Path
if ($RestoreLauncher) { $restorePath = (Resolve-Path -LiteralPath $RestoreLauncher).Path }
& $python $script --root $benchPath inspect
if ($LASTEXITCODE -ne 0) { throw 'Dedicated SQLite bench verification failed' }
if (-not $env:CONTROL_PLANE_API_KEY) {
    $secret = Read-Host 'OpenAI tunnel key (hidden; never saved)' -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}
# The runtime parses this value as a shell-style command on Windows too.
# Backslashes are escape characters there, even inside quoted paths.
$command = 'command="' + $python.Replace('\', '/') + '" "' + $script.Replace('\', '/') + '" --root "' + $benchPath.Replace('\', '/') + '" serve'
Write-Host 'Starting isolated AIR P07 bench. The health-insurance pilot is unchanged. Ctrl+C to stop.'
while ($true) {
    if ($RestoreLauncher -and (Test-Path -LiteralPath (Join-Path $benchPath 'restore-pilot.signal'))) {
        Write-Host 'Restoring the original pilot launcher with the key kept in this console.'
        & $restorePath -TunnelId $TunnelId
        break
    }
    & $runtimePath run --control-plane.tunnel-id $TunnelId --mcp.command $command --mcp.stdio-send-initialized-notification --health.listen-addr 127.0.0.1:0 --log.file (Join-Path $benchPath 'tunnel.log')
    Start-Sleep -Seconds 3
}
