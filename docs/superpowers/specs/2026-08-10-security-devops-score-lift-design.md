# Security, DevOps-C, and Score Lift Design

**Date:** 2026-08-10  
**Status:** Approved for planning  
**Target:** Weighted overall architecture score ≈ **8.5 / 10**  
**DevOps mode:** **C** — CI, docs, hardening, GitHub push; no host-specific deploy / no Docker in this effort

## Context

Architecture audit scored Ziuza at **~6.3 / 10**. Security (**4.5**) and DevOps (**4.0**) were the largest drags. Option **B** expands beyond security + DevOps-C with the **minimum** extra work (data integrity, tests, observability baseline, a11y/UI stubs) required to reach ≈8.5 overall.

The workspace is **not yet a git repository**. First push target:  
`https://github.com/MukoyaKuya/Ziuza-Market-Place`

## Goals

1. Close critical/high payment and redirect security findings with regression tests.
2. Initialize git, harden ignore/secrets hygiene, strengthen CI, push to GitHub.
3. Fix checkout/payment/cart integrity gaps that threaten data and security posture.
4. Add lightweight observability and high-leverage a11y/UI fixes.
5. Leave the modular monolith (Django + HTMX + Alpine + Tailwind + services/selectors) intact.

## Non-goals

- Docker / Compose / Kubernetes
- Host-specific IaC (Railway, Render, Fly, VPS playbooks beyond a generic runbook)
- Celery / worker rewrite (document cron; do not introduce a queue yet)
- S3/CDN implementation (document only)
- React / SPA migration
- Broad design-system rewrite of every page

## Target scorecard (estimated after this work)

| Category | From | To (est.) | How |
|---|---:|---:|---|
| Security | 4.5 | ≥8.5 | Callback trust, redirects, uploads, error leakage, design-system gate |
| DevOps | 4.0 | ≥7.5 | GitHub, CI, honest hardening, deploy runbook, prod settings knobs |
| Database | 5.5 | ≥7.5 | Constraints, checkout lock, payment uniqueness |
| Testing | 6.5 | ≥8.0 | Payment IDOR, redirects, prod payment config, integrity |
| Observability | 5.0 | ≥7.0 | Request ID + Sentry-required-in-prod docs/settings |
| Accessibility | 5.5 | ≥7.0 | Skip link, aria-expanded, password type, stub hearts |
| Tailwind / Design | 6.0 | ≥7.0 | `btn-outline` defined |
| **Weighted overall** | **6.3** | **≈8.5** | Security/DB/testing weighted heavily |

## Architecture decisions

### Payment trust boundary

- `fake_callback` must **never** confirm non-fake payments.
- `FakePaymentProvider.process_callback` must filter `provider='fake'`.
- Outside `DEBUG`, `fake_callback` returns **404** (route may remain for URL stability, but is dead in prod).
- Production requires `MPESA_LIVE=True` when `PAYMENT_PROVIDER=mpesa`.
- M-Pesa callback signature verification requires authenticated callback whenever secret is configured **or** live mode is on; production always has secret + live.
- Client-facing callback errors return generic messages; details go to logs only.
- Fake payment references must be unique per attempt (include nonce) so FAILED → retry works.
- At most one **confirmed** payment per order (partial UniqueConstraint).

### Redirect safety

- All `next` / post-login redirects use Django’s `url_has_allowed_host_and_scheme` (or `redirect_to_login` pattern) with `allowed_hosts={request.get_host()}`.

### Uploads

- Digital assets reuse the evidence-style MIME allowlist + magic-byte check + size cap (PDF + common archive/doc types as product requires; start with PDF + zip + common image types used for digital goods, documented in service).

### Checkout integrity

- `create_checkout_order` locks the cart row (`select_for_update`) before reading lines/reserving stock.
- Unique cart per authenticated user (and unique anonymous session cart when `session_key` non-empty).
- Replace nullable `unique_together` on `CartItem` with conditional UniqueConstraints so NULL variants cannot duplicate.

### DevOps-C

- `git init` → commit → remote → push `main`.
- Ensure `.gitignore` covers `.env`, `db.sqlite3`, `.venv`, `media/`, `private_media/`, secrets.
- CI keeps migrate check + pytest; add a lightweight secret-scan or documented checklist step if feasible without new heavy deps.
- `docs/production-hardening.md` corrected (payment authenticity not “done” until this work lands).
- New `docs/deploy-runbook.md`: env vars, gunicorn, cron commands, health checks — host-agnostic.
- Production settings: `CSRF_TRUSTED_ORIGINS` from env; optional `SECURE_PROXY_SSL_HEADER`.

### Observability

- Middleware adds `X-Request-ID` (generate or honor incoming) and attach to logging via `logging.Filter` / contextvars.
- Production: if `SENTRY_DSN` unset, log a loud warning at startup (do not hard-crash; document as required for true prod).

### A11y / UI stubs

- Skip link to `#main-content`.
- Navbar toggles: `aria-expanded` / `aria-controls`.
- Login/register: static `type="password"` with Alpine enhancement.
- `listing_card` favorite: remove stub or wire to real endpoint with progressive enhancement.
- Define `.btn-outline` in `static/src/input.css` (rebuild CSS).

## Testing strategy

New/extended tests under `tests/`:

- Fake callback cannot confirm M-Pesa payment
- Fake callback 404 when `DEBUG=False`
- Open redirect rejected on login
- Production settings refuse `MPESA_LIVE=False` with mpesa
- Checkout concurrent double-submit does not create two orders (or second fails cleanly)
- Digital asset rejects spoofed content-type
- Existing commerce suite remains green

## Risks

| Risk | Mitigation |
|---|---|
| Constraint migrations fail on dirty local data | Data cleanup migration or document wipe for local SQLite |
| Push to non-empty GitHub repo | Check remote; if history exists, coordinate force/rebase with user — never force without explicit ask |
| CSS rebuild forgotten | Plan step runs `npm run build:css`; note `styles.css` is gitignored — document that deploy must build CSS |
| Over-scoping a11y | Cap at listed quick wins |

## Success criteria

- [ ] Critical payment findings closed; tests green in CI
- [ ] Repo on GitHub without secrets
- [ ] Hardening checklist accurate
- [ ] Deploy runbook published
- [ ] Re-audit estimate meets table above (≈8.5 overall)

## Delivery order

1. Security + payment/redirect tests  
2. Git init + GitHub + CI/docs  
3. DB/checkout integrity + migrations  
4. Observability + a11y/UI polish  
5. Final pytest + push
