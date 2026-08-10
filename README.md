# Ziuza Marketplace

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

Run `python manage.py expire_order_reservations` on a recurring schedule (at
least once per minute) so abandoned checkouts promptly return stock to sale.
Run `python manage.py notify_low_stock` daily so sellers receive one alert when
an active listing reaches its configured stock threshold; restocking resets it.
Run `python manage.py process_saved_search_alerts` and
`python manage.py process_discovery_alerts` every 10–15 minutes to create buyer
notifications for new search matches, followed-shop listings, price changes,
and back-in-stock events. Run `python manage.py deliver_notifications` through
a recurring worker to deliver queued notification emails.
Run `python manage.py process_review_reminders` daily to invite buyers to leave
a verified review three days after confirmed delivery.
Run `python manage.py rollup_shop_analytics` daily (and optionally
`python manage.py rollup_shop_analytics --backfill --days 30` after deploy)
so seller analytics charts stay filled for shops with paid orders.

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
| `PAYMENT_PROVIDER` | `fake` (default) or `mpesa` (Daraja scaffold) |
| `MPESA_*` | Daraja credentials, public callback URL, and callback secret |
| `SENTRY_DSN` | Optional; enables Sentry in production when `sentry-sdk` is installed |

Settings live under `config/settings/` (`base`, `local`, `test`, `production`).

### M-Pesa sandbox

Create a sandbox app in the Safaricom Daraja portal, then set:

```text
PAYMENT_PROVIDER=mpesa
MPESA_DARAJA_ENABLED=True
MPESA_LIVE=False
MPESA_CONSUMER_KEY=...
MPESA_CONSUMER_SECRET=...
MPESA_SHORTCODE=174379
MPESA_PASSKEY=...
MPESA_CALLBACK_URL=https://your-public-host/payments/callback/mpesa/
MPESA_CALLBACK_SECRET=a-long-random-token
```

The application appends the callback token to the registered callback URL,
normalizes Kenyan phone numbers, obtains an OAuth token, and submits the STK
Push. The callback still verifies the checkout reference and exact order amount.
Localhost is not reachable by Daraja; use an HTTPS deployment or tunnel for
sandbox callback testing.

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

### Security hardening 2026-08-10

Completed the [security / DevOps-C score-lift plan](docs/superpowers/plans/2026-08-10-security-devops-score-lift.md) per the [design spec](docs/superpowers/specs/2026-08-10-security-devops-score-lift-design.md): payment callback trust, redirect safety, upload validation, checkout/cart integrity, CI + runbook, request ID observability, and baseline a11y/UI fixes. Estimated re-audit: weighted overall ≈8.5/10 (see spec scorecard addendum).

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
