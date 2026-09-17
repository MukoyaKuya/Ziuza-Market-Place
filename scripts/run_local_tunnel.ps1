param(
    [int]$Port = 8010
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'var\selfhost-venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing virtual environment interpreter: $python"
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/live/" -TimeoutSec 5
        if ($health.status -eq 'live') {
            Write-Host "Ziuza is already running on http://127.0.0.1:$Port (process $($listener.OwningProcess))."
            exit 0
        }
    }
    catch {
        # The listener is not a healthy Ziuza server; report the port conflict below.
    }
    throw "Port $Port is occupied by process $($listener.OwningProcess), but Ziuza's health check failed."
}

Push-Location $projectRoot
try {
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.tunnel_testing'
    $env:REQUIRE_EMAIL_VERIFICATION = 'False'

    Write-Warning 'TESTING PROFILE: SQLite and fake payments are enabled. Do not accept real orders.'
    Write-Host 'Collecting static files...'
    & $python manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) {
        throw 'Static file collection failed.'
    }

    Write-Host 'Checking database migrations...'
    & $python manage.py migrate --check
    if ($LASTEXITCODE -ne 0) {
        throw 'Database migrations are pending. Run: manage.py migrate'
    }

    Write-Host "Starting Ziuza on http://127.0.0.1:$Port"
    Write-Host 'Keep this window open. Press Ctrl+C to stop the server.'
    & $python -m waitress "--listen=127.0.0.1:$Port" 'config.wsgi:application'
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
