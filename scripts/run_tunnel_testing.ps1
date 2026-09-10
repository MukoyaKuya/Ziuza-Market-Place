$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'var\selfhost-venv\Scripts\python.exe'
$logDirectory = Join-Path $projectRoot 'var\logs'
$logFile = Join-Path $logDirectory 'tunnel-testing.log'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run the local setup first so var\selfhost-venv exists.'
}

$existingListener = Get-NetTCPConnection -State Listen -LocalAddress 127.0.0.1 -LocalPort 8010 -ErrorAction SilentlyContinue
if ($existingListener) {
    Write-Output 'Ziuza tunnel testing server is already listening on 127.0.0.1:8010.'
    exit 0
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
"[$(Get-Date -Format o)] Starting temporary Ziuza tunnel testing server on 127.0.0.1:8010." | Tee-Object -FilePath $logFile -Append
Write-Warning 'This profile uses SQLite and fake payments. Do not accept real orders on ziuza.shop.'

$env:DJANGO_SETTINGS_MODULE = 'config.settings.tunnel_testing'
$PSNativeCommandUseErrorActionPreference = $false
& $python -m waitress `
  --listen=127.0.0.1:8010 `
  --trusted-proxy=127.0.0.1 `
  --trusted-proxy-headers="x-forwarded-proto" `
  config.wsgi:application 2>&1 | Tee-Object -FilePath $logFile -Append
