# Phase 15 — Production Hardening Checklist

Use before production release. High-debt seller dashboard pages and analytics charts are polished; remaining lower-priority seller UI polish is iterative.

**Score-lift pass (2026-08-10):** payment trust boundary, redirect safety, digital-asset validation, checkout/cart DB constraints, request ID + Sentry prod warning, CI/runbook, and baseline a11y stubs — see [design spec](superpowers/specs/2026-08-10-security-devops-score-lift-design.md).

## Security
- [ ] `DEBUG=False`, strong `SECRET_KEY`, locked `ALLOWED_HOSTS`
- [x] HTTPS + secure cookies (see `config/settings/production.py`)
- [x] Permissions audit on seller/buyer mutations (actor ownership) — ongoing with each service
- [x] Payment callbacks verify authenticity + idempotency (fake DEBUG gate, provider mismatch guard, M-Pesa signature when live/secret set, unique confirmed payment per order)
- [x] Open redirect blocked on login `next` (`url_has_allowed_host_and_scheme`)
- [x] Digital asset uploads validated (MIME allowlist + magic bytes + size cap)
- [x] Design-system preview gated to staff or `DEBUG`
- [x] Expired/failed/cancelled order reservations release inventory idempotently
- [x] Rate limit auth, search, payment callbacks (`SimpleRateLimitMiddleware`)
- [x] `.gitignore` covers `.env`, secrets, local DB/media (rotate any keys ever committed)

## Data & performance
- [ ] PostgreSQL in production; run migrations
- [x] Checkout locks cart row; unique cart per user/session; cart-item and inventory reserved constraints
- [ ] Query audit on search, category, cart, checkout
- [x] Cache LocMem by default; Redis optional in production
- [x] Paginate search/category list endpoints

## Observability
- [x] Structured logging foundation (`LOGGING` in settings)
- [x] Request ID middleware (`X-Request-ID` on responses; honored when client sends header)
- [x] Optional Sentry via `SENTRY_DSN` (requires `sentry-sdk` from `[prod]` extras; startup warning when unset in production)
- [x] `/health/live/` and `/health/ready/` wired
- [ ] Slow query monitoring

## SEO & a11y
- [x] Sitemap + robots
- [x] Canonical URLs on listing/shop/collection pages
- [x] Baseline a11y stubs (skip link, `aria-expanded` on nav toggles, password field types, listing-card favorites wired or omitted)
- [ ] Full WCAG AA pass on primary flows

## Ops
- [ ] Backups for Postgres + media
- [ ] `collectstatic` + CDN/object storage for media
- [x] CI: pytest + migrate check (`.github/workflows/ci.yml`)
- [x] Host-agnostic deploy runbook (`docs/deploy-runbook.md`) — includes CSS build step (`styles.css` is gitignored)
- [ ] Docker/container image (not required; runbook is host-agnostic)
- [ ] Celery/worker for email & image jobs when introduced
- [ ] Schedule `expire_order_reservations` at least once per minute
- [ ] Schedule `notify_low_stock` daily
- [ ] Schedule `process_saved_search_alerts` and `process_discovery_alerts` every 10–15 minutes
- [ ] Run `deliver_notifications` through a recurring email-delivery worker
- [ ] Schedule `process_review_reminders` daily
