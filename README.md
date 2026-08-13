# Ziuza Marketplace

[![CI](https://github.com/MukoyaKuya/Ziuza-Market-Place/actions/workflows/ci.yml/badge.svg)](https://github.com/MukoyaKuya/Ziuza-Market-Place/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0-092E20.svg?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Frontend](https://img.shields.io/badge/frontend-HTMX%20%2B%20Alpine.js-336699.svg?style=flat)](https://htmx.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Multi-vendor marketplace celebrating Kenyan creators, artisans, and producers.

**Repository:** [github.com/MukoyaKuya/Ziuza-Market-Place](https://github.com/MukoyaKuya/Ziuza-Market-Place)

**Stack:** Django 5 · server-rendered templates · HTMX · Alpine.js · Tailwind CSS · PostgreSQL (production)

## Requirements

- Python ≥ 3.12
- Node.js 18+ (Tailwind CSS build)
- PostgreSQL recommended for production-like local work (`DATABASE_URL`); SQLite is the local fallback

## Quick start

```powershell
cd Ziuza
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

copy .env.example .env

python manage.py migrate
python manage.py seed_demo --with-order

npm install
npm run build:css

python manage.py runserver
```

Run Celery worker and Celery Beat for background queue processing and periodic jobs:

```powershell
# In a separate terminal: Run Celery Worker
celery -A config worker -l info

# In a separate terminal: Run Celery Beat Scheduler
celery -A config beat -l info
```

Alternatively, tasks can still be run manually or via cron with Django management commands:
- `python manage.py expire_order_reservations` (releases abandoned cart checkouts)
- `python manage.py notify_low_stock` (daily low-stock alerts)
- `python manage.py process_saved_search_alerts` & `python manage.py process_discovery_alerts` (discovery notifications)
- `python manage.py deliver_notifications` (queued email delivery worker)
- `python manage.py process_review_reminders` (verified buyer review invitations)
- `python manage.py rollup_shop_analytics` (daily seller metrics rollup)

Demo logins after `seed_demo`:

| Role | Email | Password |
|------|-------|----------|
| Seller | seller@demo.ziuza.co.ke | DemoPassword123! |
| Buyer | buyer@demo.ziuza.co.ke | DemoPassword123! |

Useful URLs:

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/ | Homepage |
| http://127.0.0.1:8000/search/ | Search |
| http://127.0.0.1:8000/categories/ | Browse categories |
| http://127.0.0.1:8000/cart/ | Cart |
| http://127.0.0.1:8000/checkout/ | Checkout (auth) |
| http://127.0.0.1:8000/account/ | Buyer account |
| http://127.0.0.1:8000/sell/ | Start selling |
| http://127.0.0.1:8000/seller/ | Seller dashboard |
| http://127.0.0.1:8000/health/live/ | Liveness probe |
| http://127.0.0.1:8000/health/ready/ | Readiness probe (DB) |
| http://127.0.0.1:8000/sitemap.xml | Sitemap |
| http://127.0.0.1:8000/admin/ | Django admin |

Watch CSS during UI work:

```powershell
npm run watch:css
```

## Configuration

| Variable | Notes |
|----------|--------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.local` (default), `.test`, or `.production` |
| `SECRET_KEY` | Required; never commit real secrets |
| `DEBUG` | `True` for local only |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| `DATABASE_URL` | PostgreSQL URL; if unset in local, uses SQLite |
| `REDIS_URL` | Optional; LocMem cache used when unset |
| `CELERY_BROKER_URL` | Redis URL for Celery message broker (`redis://127.0.0.1:6379/0` by default) |
| `PAYMENT_PROVIDER` | `fake` (default) or `mpesa` (Daraja scaffold) |
| `MPESA_*` | Daraja credentials, public callback URL, and callback secret |
| `SENTRY_DSN` | Optional; enables Sentry in production when `sentry-sdk` is installed |

Settings live under `config/settings/` (`base`, `local`, `test`, `production`).

## Architecture

```
apps/
  core/           # Home, health, errors, rate limits, sitemaps
  accounts/       # Custom User, auth, profile, addresses
  marketplace/
    shops/        # Shops + seller dashboard shell
    categories/   # Category tree
    listings/     # Catalog + inventory
    content/      # Homepage CMS
    search/       # Discovery
    favorites/    # Wishlist
    cart/         # Cart
    orders/       # Checkout + buyer/seller orders
    payments/     # Fake + M-Pesa provider interface
    shipping/     # Methods + fulfillment
    reviews/      # Verified purchase reviews
    notifications/
    messaging/
    analytics/
    promotions/   # Seller coupons + reservation-aware redemption limits
components/       # Reusable template partials
templates/        # Layouts + pages
config/           # Settings, URLs, WSGI/ASGI
tests/            # pytest suite
docs/             # Engineering notes + hardening checklist
```

Rules of thumb (see PRD):

- Thin views · explicit services · reusable selectors
- HTMX for server-driven partials · Alpine for UI-only state
- No business logic in templates or JavaScript

Component conventions: [docs/component-conventions.md](docs/component-conventions.md)  
Production checklist: [docs/production-hardening.md](docs/production-hardening.md)  
Deploy runbook: [docs/deploy-runbook.md](docs/deploy-runbook.md)

## Tests

```powershell
pytest
```

## Production notes

See [docs/deploy-runbook.md](docs/deploy-runbook.md) for the full host-agnostic checklist (env vars, CSS build, cron, health probes). Summary:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
# Set DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, PAYMENT_PROVIDER, etc.
pip install -e ".[prod]"
npm ci; npm run build:css   # styles.css is gitignored — required every deploy
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

## Current status

Phases 0–15 MVP flows are implemented (accounts → shops → catalog → CMS → search → cart → checkout → payments → shipping → reviews → messaging → analytics → hardening basics). High-debt seller dashboard pages (reviews, promotions, messages, custom orders, verification, order detail) and analytics charts with persisted daily metrics are polished; remaining polish on lower-priority seller sections is iterative.
