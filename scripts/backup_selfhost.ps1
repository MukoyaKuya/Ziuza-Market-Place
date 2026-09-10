param(
    [string]$BackupRoot = '',
    [int]$RetentionDays = 30
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $BackupRoot) {
    $BackupRoot = Join-Path $projectRoot 'var\backups'
}
if (-not $env:DATABASE_URL) {
    throw 'DATABASE_URL must be exported for pg_dump.'
}
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
    throw 'pg_dump is not available on PATH.'
}

$parent = Split-Path -Parent $BackupRoot
if (-not (Test-Path -LiteralPath $parent)) {
    throw "Backup parent does not exist: $parent"
}
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$temporary = Join-Path $BackupRoot ".ziuza-$stamp.tmp"
$final = Join-Path $BackupRoot "ziuza-$stamp"
New-Item -ItemType Directory -Path $temporary | Out-Null

try {
    $databaseFile = Join-Path $temporary 'database.dump'
    & pg_dump --dbname=$env:DATABASE_URL --format=custom --file=$databaseFile
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE." }

    foreach ($directory in @('media', 'private_media')) {
        $source = Join-Path $projectRoot $directory
        if (Test-Path -LiteralPath $source) {
            Compress-Archive -Path $source -DestinationPath (Join-Path $temporary "$directory.zip") -CompressionLevel Optimal
        }
    }

    $files = Get-ChildItem -LiteralPath $temporary -File | ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        @{ Name = $_.Name; SHA256 = $hash.Hash }
    }
    @{ CreatedAt = (Get-Date).ToUniversalTime().ToString('o'); Files = @($files) } |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $temporary 'manifest.json') -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $final
} catch {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    throw
}

$cutoff = (Get-Date).AddDays(-[Math]::Max(1, $RetentionDays))
Get-ChildItem -LiteralPath $BackupRoot -Directory |
    Where-Object { $_.Name -like 'ziuza-*' -and $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Recurse -Force

$final
