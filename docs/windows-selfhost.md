# Windows Self-Host Operations

The public self-host profile requires PostgreSQL, Redis, production M-Pesa settings, and
the hardened `config.settings.selfhost` profile. SQLite and fake payments are rejected.

Run these as separate supervised processes:

```powershell
.\scripts\run_selfhost.ps1
.\scripts\run_selfhost_worker.ps1
.\scripts\run_selfhost_beat.ps1
```

Celery's conservative Windows configuration is `--pool=solo --concurrency=1`. Run exactly
one Beat process. Install each launcher with a Windows service manager such as WinSW or
NSSM using a restricted service account, the repository as working directory, automatic
restart with backoff, and rotated logs. Cloudflare Tunnel, PostgreSQL, and Redis must also
start before Ziuza.

Before restart:

```powershell
.\var\selfhost-venv\Scripts\python.exe manage.py migrate
.\var\selfhost-venv\Scripts\python.exe manage.py collectstatic --noinput
.\var\selfhost-venv\Scripts\python.exe manage.py ops_preflight
```

After restart, check `/health/live/` and `/health/ready/?check_celery=1`. A port listener
alone is not a health check. Keep service-manager credentials and Cloudflare tokens outside
the repository.
