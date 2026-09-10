param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [Parameter(Mandatory = $true)][string]$TargetDatabaseUrl,
    [Parameter(Mandatory = $true)][string]$MediaRestoreRoot,
    [switch]$ConfirmRestore
)

$ErrorActionPreference = 'Stop'
if (-not $ConfirmRestore) {
    throw 'Pass -ConfirmRestore after verifying the target is an empty drill database and isolated media directory.'
}
if (-not (Test-Path -LiteralPath $BackupPath -PathType Container)) {
    throw "Backup directory does not exist: $BackupPath"
}
if (Test-Path -LiteralPath $MediaRestoreRoot) {
    throw 'MediaRestoreRoot must not already exist.'
}
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
    throw 'pg_restore is not available on PATH.'
}

$manifestPath = Join-Path $BackupPath 'manifest.json'
$databaseFile = Join-Path $BackupPath 'database.dump'
if (-not (Test-Path -LiteralPath $manifestPath) -or -not (Test-Path -LiteralPath $databaseFile)) {
    throw 'Backup is missing manifest.json or database.dump.'
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.Files) {
    $path = Join-Path $BackupPath $file.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Backup file is missing: $($file.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($actual -ne $file.SHA256) { throw "Checksum mismatch: $($file.Name)" }
}

& pg_restore --exit-on-error --no-owner --dbname=$TargetDatabaseUrl $databaseFile
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE." }

New-Item -ItemType Directory -Path $MediaRestoreRoot | Out-Null
foreach ($archiveName in @('media.zip', 'private_media.zip')) {
    $archive = Join-Path $BackupPath $archiveName
    if (Test-Path -LiteralPath $archive) {
        Expand-Archive -LiteralPath $archive -DestinationPath $MediaRestoreRoot
    }
}

'Restore completed. Run Django checks and application smoke tests against the isolated restore target.'
