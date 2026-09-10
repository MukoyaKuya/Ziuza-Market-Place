$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'var\selfhost-venv\Scripts\python.exe'
$scheduleDirectory = Join-Path $projectRoot 'var\celery'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run the self-host setup first so var\selfhost-venv exists.'
}
if (-not (Test-Path -LiteralPath (Split-Path -Parent $scheduleDirectory))) {
    throw 'Expected the project var directory to exist.'
}
New-Item -ItemType Directory -Path $scheduleDirectory -Force | Out-Null

$env:DJANGO_SETTINGS_MODULE = 'config.settings.selfhost'
& $python -m celery -A config beat --loglevel=info --schedule (Join-Path $scheduleDirectory 'beat-schedule')
