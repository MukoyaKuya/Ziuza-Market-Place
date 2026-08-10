# Deploy Runbook (host-agnostic)

Use this checklist when deploying Ziuza to any Linux/Windows host, VM, or PaaS. It does not assume Docker, Celery, or a specific cloud provider.

## Prerequisites

- Python ≥ 3.12
- Node.js 18+ (Tailwind CSS build only; not needed at runtime)
- PostgreSQL (required in production)
- Reverse proxy with TLS (nginx, Caddy, load balancer, etc.)

## 1. Environment variables

Copy `.env.example` to `.env` on the server (never commit `.env`). Set at minimum:

| Variable | Required | Notes |
|----------|----------|-------|
| `DJANGO_SETTINGS_MODULE` | Yes | `config.settings.production` |
| `SECRET_KEY` | Yes | Long random string; rotate if leaked |
| `DEBUG` | Yes | Must be `False` in production |
| `ALLOWED_HOSTS` | Yes | Comma-separated hostnames (e.g. `ziuza.co.ke,www.ziuza.co.ke`) |
| `CSRF_TRUSTED_ORIGINS` | Yes | HTTPS origins (e.g. `https://ziuza.co.ke,https://www.ziuza.co.ke`) |
| `DATABASE_URL` | Yes | PostgreSQL URL (`postgres://user:pass@host:5432/dbname`) |
| `PAYMENT_PROVIDER` | Yes | `fake` (sandbox) or `mpesa` |
| `MPESA_*` | If M-Pesa | See `.env.example` for details; production requires `MPESA_LIVE=True` |
| `REDIS_URL` | Optional | Enables Redis cache when set; LocMem otherwise |
| `SENTRY_DSN` | Optional | Error tracking when `sentry-sdk` is installed via `[prod]` |
| `PUBLIC_SITE_URL` | Recommended | Canonical site URL for emails and links |
| `DEFAULT_FROM_EMAIL` | Recommended | Sender for notification emails |
| `DJANGO_BEHIND_PROXY` | If behind proxy | Set `True` when TLS terminates at a reverse proxy |

See [`.env.example`](../.env.example) for the full list including SMTP and security toggles.

## 2. Install application dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[prod]"
```

The `[prod]` extra installs `gunicorn`, `redis`, and `sentry-sdk[django]`.

## 3. Build frontend assets

**`static/css/styles.css` is gitignored.** Every deploy must compile Tailwind CSS or pages will load without styles.

```bash
npm ci
npm run build:css
```

Source: `static/src/input.css` → output: `static/css/styles.css`.

## 4. Database and static files

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate
python manage.py collectstatic --noinput
```

Run migrations before serving traffic. Re-run `collectstatic` after upgrades that change static assets.

Optional one-time analytics backfill after first deploy:

```bash
python manage.py rollup_shop_analytics --backfill --days 30
```

## 5. Run the web process

Serve WSGI with Gunicorn (included in `[prod]`):

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

Tune `--workers` and `--timeout` for your host. Put Gunicorn behind a reverse proxy that terminates TLS and forwards `X-Forwarded-Proto` when `DJANGO_BEHIND_PROXY=True`.

## 6. Scheduled management commands

Configure cron, systemd timers, or your platform's scheduler. All commands assume the project venv is activated and `DJANGO_SETTINGS_MODULE=config.settings.production`.

| Schedule | Command | Purpose |
|----------|---------|---------|
| Every minute | `python manage.py expire_order_reservations` | Release stock from abandoned checkouts |
| Daily | `python manage.py notify_low_stock` | Alert sellers when listings hit low-stock threshold |
| Every 10–15 min | `python manage.py process_saved_search_alerts` | Buyer notifications for saved-search matches |
| Every 10–15 min | `python manage.py process_discovery_alerts` | Alerts for followed shops, price drops, back-in-stock |
| Recurring (e.g. every 5 min) | `python manage.py deliver_notifications` | Send queued notification emails |
| Daily | `python manage.py process_review_reminders` | Invite buyers to review after delivery |
| Daily | `python manage.py rollup_shop_analytics` | Persist seller analytics chart data |

Example crontab entries (adjust paths):

```cron
* * * * * cd /srv/ziuza && .venv/bin/python manage.py expire_order_reservations
0 8 * * * cd /srv/ziuza && .venv/bin/python manage.py notify_low_stock
*/10 * * * * cd /srv/ziuza && .venv/bin/python manage.py process_saved_search_alerts
*/10 * * * * cd /srv/ziuza && .venv/bin/python manage.py process_discovery_alerts
*/5 * * * * cd /srv/ziuza && .venv/bin/python manage.py deliver_notifications
0 9 * * * cd /srv/ziuza && .venv/bin/python manage.py process_review_reminders
30 2 * * * cd /srv/ziuza && .venv/bin/python manage.py rollup_shop_analytics
```

Celery/workers are not required today; these commands run as one-off cron jobs.

## 7. Health checks

| Endpoint | Use | Success |
|----------|-----|---------|
| `/health/live/` | Liveness — process is up | HTTP 200, `{"status":"live",...}` |
| `/health/ready/` | Readiness — DB reachable | HTTP 200 when DB OK; HTTP 503 otherwise |

Point load balancer or orchestrator probes at these paths.

## 8. Post-deploy verification

- [ ] Homepage and a listing page render with CSS (confirms `npm run build:css` ran)
- [ ] `/health/live/` and `/health/ready/` return 200
- [ ] Login, search, and checkout smoke test
- [ ] Cron entries installed and logging to a known location
- [ ] No `.env` or secrets committed to git

## Related docs

- [Production hardening checklist](production-hardening.md)
- [README](../README.md) — local dev, M-Pesa sandbox, architecture
