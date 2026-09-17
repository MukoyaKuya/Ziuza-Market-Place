$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'var\selfhost-venv\Scripts\python.exe'
$envFile = Join-Path $projectRoot '.env'
$logDirectory = Join-Path $projectRoot 'var\logs'
$logFile = Join-Path $logDirectory 'selfhost.log'

if (-not (Test-Path $python)) {
    throw 'Run the self-host setup first so var\\selfhost-venv exists.'
}

$existingListener = Get-NetTCPConnection -State Listen -LocalAddress 127.0.0.1 -LocalPort 8010 -ErrorAction SilentlyContinue
if ($existingListener) {
    Write-Output 'Ziuza self-host server is already listening on 127.0.0.1:8010.'
    exit 0
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
"[$(Get-Date -Format o)] Starting Ziuza self-host server on 127.0.0.1:8010." | Tee-Object -FilePath $logFile -Append

$paymentProvider = ''
if (Test-Path -LiteralPath $envFile) {
    $providerLine = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match '^\s*PAYMENT_PROVIDER\s*=' } |
        Select-Object -Last 1
    if ($providerLine) {
        $paymentProvider = ($providerLine -split '=', 2)[1].Trim().Trim('"').Trim("'").ToLowerInvariant()
    }
}

if ($paymentProvider -eq 'fake') {
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.tunnel_testing'
    Write-Warning 'Starting the temporary tunnel-testing profile with SQLite and fake payments. Do not accept real orders.'
} else {
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.selfhost'
}
# Waitress writes its ordinary startup/access logs to stderr.  A PowerShell
# profile can opt into treating native stderr as a terminating error; keep
# those log records in the merged stream below instead.
$PSNativeCommandUseErrorActionPreference = $false
& $python -m waitress `
  --listen=127.0.0.1:8010 `
  --trusted-proxy=127.0.0.1 `
  --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" `
  config.wsgi:application 2>&1 | Tee-Object -FilePath $logFile -Append
