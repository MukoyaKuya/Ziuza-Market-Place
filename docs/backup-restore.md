# Backup And Restore

Backups are an operator-owned production dependency. A backup is not complete until it
is encrypted, copied off-host, monitored, and restored successfully in a drill.

## Protected Assets

- PostgreSQL database, using a custom-format `pg_dump`.
- Public media when filesystem storage is used.
- Private digital assets and buyer-protection evidence.
- Deployment environment and secrets through the secret manager, never in backup archives.

For S3-compatible media, enable bucket versioning and lifecycle protection instead of
copying live buckets through the application host.

## PostgreSQL Backup

```bash
pg_dump --dbname="$DATABASE_URL" --format=custom --file="ziuza-$(date +%Y%m%d-%H%M%S).dump"
sha256sum ziuza-*.dump > SHA256SUMS
```

Copy the dump and checksum to encrypted off-host storage. Set retention only after Kenyan
tax, payment, privacy, and dispute requirements are approved.

Windows self-host deployments can create the same database/media bundle with:

```powershell
$env:DATABASE_URL = 'postgres://...'
.\scripts\backup_selfhost.ps1 -BackupRoot D:\ZiuzaBackups -RetentionDays 30
```

## Restore Drill

Always restore into a new empty database. Never test against production.

```bash
sha256sum --check SHA256SUMS
createdb ziuza_restore_drill
pg_restore --exit-on-error --no-owner --dbname=ziuza_restore_drill ziuza-YYYYMMDD-HHMMSS.dump
DATABASE_URL=postgres://.../ziuza_restore_drill python manage.py migrate --check
DATABASE_URL=postgres://.../ziuza_restore_drill python manage.py check
```

Restore filesystem media into an isolated directory, verify authorized private downloads,
then destroy the drill environment. Record drill date, duration, backup age, row counts,
media samples, and failures. Run at least quarterly and after major schema/storage changes.

On Windows, the guarded restore helper requires an empty target and a new media directory:

```powershell
.\scripts\restore_selfhost.ps1 -BackupPath D:\ZiuzaBackups\ziuza-YYYYMMDD-HHMMSS `
  -TargetDatabaseUrl 'postgres://.../ziuza_restore_drill' `
  -MediaRestoreRoot D:\ZiuzaRestoreDrill -ConfirmRestore
```

## Required Operator Decisions

- Recovery point objective and recovery time objective.
- Backup frequency, retention, encryption keys, and off-host provider.
- Alert destination for failed or stale backups.
- Database role allowed to dump and restore.
- Object-storage versioning, replication, and lifecycle policy.
