# Phase 15 — Production Hardening Checklist

Use before production release. High-debt seller dashboard pages and analytics charts are polished; remaining lower-priority seller UI polish is iterative.

## Security
- [ ] `DEBUG=False`, strong `SECRET_KEY`, locked `ALLOWED_HOSTS`
- [x] HTTPS + secure cookies (see `config/settings/production.py`)
- [x] Permissions audit on seller/buyer mutations (actor ownership) — ongoing with each service
- [x] Payment callbacks verify authenticity + idempotency (Fake + M-Pesa scaffold)
- [x] Expired/failed/cancelled order reservations release inventory idempotently
- [x] Rate limit auth, search, payment callbacks (`SimpleRateLimitMiddleware`)
- [ ] No secrets in git; rotate any leaked keys

## Data & performance
- [ ] PostgreSQL in production; run migrations
- [ ] Query audit on search, category, cart, checkout
- [x] Cache LocMem by default; Redis optional in production
- [x] Paginate search/category list endpoints

## Observability
- [x] Structured logging foundation (`LOGGING` in settings)
- [x] Optional Sentry via `SENTRY_DSN` (requires `sentry-sdk` from `[prod]` extras)
- [x] `/health/live/` and `/health/ready/` wired
- [ ] Slow query monitoring

## SEO & a11y
- [x] Sitemap + robots
- [x] Canonical URLs on listing/shop/collection pages
- [ ] WCAG AA pass on primary flows

## Ops
- [ ] Backups for Postgres + media
- [ ] `collectstatic` + CDN/object storage for media
- [x] CI: pytest + migrate check (`.github/workflows/ci.yml`)
- [ ] Celery/worker for email & image jobs when introduced
- [ ] Schedule `expire_order_reservations` at least once per minute
- [ ] Schedule `notify_low_stock` daily
- [ ] Schedule `process_saved_search_alerts` and `process_discovery_alerts` every 10–15 minutes
- [ ] Run `deliver_notifications` through a recurring email-delivery worker
- [ ] Schedule `process_review_reminders` daily
