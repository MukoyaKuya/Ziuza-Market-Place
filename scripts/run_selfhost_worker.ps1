$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'var\selfhost-venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run the self-host setup first so var\selfhost-venv exists.'
}

$env:DJANGO_SETTINGS_MODULE = 'config.settings.selfhost'
& $python -m celery -A config worker --loglevel=info --pool=solo --concurrency=1
