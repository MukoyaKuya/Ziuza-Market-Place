# Security, DevOps-C, and Score Lift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close critical security findings, initialize/push GitHub under DevOps mode C, and apply the minimum integrity/observability/a11y fixes to reach a weighted overall architecture score ≈ 8.5/10.

**Architecture:** Keep the Django modular monolith (services/selectors, HTMX/Alpine/Tailwind). Harden the payment trust boundary and production settings; add DB constraints and checkout locking; ship host-agnostic CI/docs + first GitHub push (no Docker).

**Tech Stack:** Django 5, pytest-django, PostgreSQL/SQLite, existing payment providers, GitHub Actions, Tailwind CLI.

**Spec:** `docs/superpowers/specs/2026-08-10-security-devops-score-lift-design.md`

## Global Constraints

- Python ≥ 3.12; Django ≥ 5.0,<6.0
- Do not introduce Docker, Celery, React, or S3 implementations
- Do not force-push to GitHub unless the user explicitly requests it
- Do not commit `.env`, secrets, `db.sqlite3`, `media/`, `private_media/`, `.venv/`
- Prefer TDD: failing test → implement → pass → commit
- Preserve services/selectors and shop RBAC patterns
- `static/css/styles.css` is gitignored — run `npm run build:css` after CSS source changes; document for deploy

## File map

| File | Responsibility |
|---|---|
| `apps/marketplace/payments/providers.py` | Provider filter, LIVE signature, unique fake refs, safe confirm |
| `apps/marketplace/payments/views.py` | DEBUG gate on fake_callback; generic callback errors |
| `apps/marketplace/payments/models.py` | Partial unique confirmed payment; PROTECT order FK if safe |
| `apps/accounts/views/__init__.py` | Safe `next` redirect |
| `apps/marketplace/listings/services.py` | Digital asset MIME/magic/size validation |
| `apps/marketplace/orders/services.py` | Cart lock at checkout |
| `apps/marketplace/cart/models.py` | Unique cart + conditional CartItem constraints |
| `apps/marketplace/listings/models/` | Inventory CheckConstraint |
| `config/settings/production.py` | MPESA_LIVE, CSRF_TRUSTED_ORIGINS, proxy SSL, Sentry warn |
| `apps/core/middleware.py` | Request ID middleware (new class or extend) |
| `apps/core/views/design_system.py` | Staff/DEBUG gate |
| `templates/layouts/base.html` | Skip link |
| `templates/layouts/navbar.html` | aria-expanded |
| `templates/accounts/login.html`, `register.html` | Static password type |
| `components/listing_card/listing_card.html` | Remove/fix favorite stub |
| `static/src/input.css` | `.btn-outline` |
| `.gitignore` | `private_media/` |
| `.github/workflows/ci.yml` | Keep/strengthen CI |
| `docs/production-hardening.md` | Honest checklist |
| `docs/deploy-runbook.md` | Host-agnostic deploy + cron |
| `tests/test_payment_security.py` | New security tests |
| `tests/test_accounts.py` | Open redirect cases |
| `tests/test_checkout_integrity.py` | Checkout lock / constraints |
| `tests/test_digital_assets.py` | Upload validation |

---

### Task 1: Payment callback security (fake path)

**Files:**
- Modify: `apps/marketplace/payments/providers.py`
- Modify: `apps/marketplace/payments/views.py`
- Create: `tests/test_payment_security.py`

**Interfaces:**
- Consumes: `FakePaymentProvider.process_callback`, `Payment` model, `get_provider`
- Produces: Fake callbacks only confirm `provider='fake'`; `fake_callback` returns 404 when `DEBUG=False`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_payment_security.py
import pytest
from django.test import Client, override_settings
from decimal import Decimal

# Use existing factories/patterns from test_commerce_flow.py:
# create buyer, order with pending mpesa payment, then POST fake callback.

@pytest.mark.django_db
def test_fake_callback_cannot_confirm_mpesa_payment(commerce_order_with_mpesa_pending):
    """POST /payments/callback/fake/ with mpesa CheckoutRequestID must not mark paid."""
    order, payment = commerce_order_with_mpesa_pending
    client = Client()
    resp = client.post(
        '/payments/callback/fake/',
        data={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        },
    )
    assert resp.status_code in (400, 404)
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.status != 'confirmed'
    assert order.payment_status != 'paid'


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_fake_callback_404_when_not_debug(commerce_order_with_fake_pending):
    order, payment = commerce_order_with_fake_pending
    client = Client()
    resp = client.post(
        '/payments/callback/fake/',
        data={
            'provider_reference': payment.provider_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
        },
    )
    assert resp.status_code == 404
```

Adapt fixtures to match existing helpers in `tests/test_commerce_flow.py` (copy minimal setup rather than inventing undeclared fixtures).

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_payment_security.py -v`  
Expected: FAIL (fake path currently confirms any reference / works with DEBUG=False)

- [ ] **Step 3: Implement provider + view guards**

In `FakePaymentProvider.process_callback`, after `select_for_update().get(...)`:

```python
if payment.provider != self.code:
    raise ValidationError('Payment provider mismatch.')
```

In `fake_callback`:

```python
from django.conf import settings
from django.http import Http404

@csrf_exempt
@require_POST
def fake_callback(request):
    if not settings.DEBUG:
        raise Http404()
    ...
    try:
        payment = provider.process_callback(payload=payload)
    except Exception:
        logging.getLogger(__name__).exception('fake_callback failed')
        return JsonResponse({'ok': False, 'error': 'callback_rejected'}, status=400)
```

Also use generic errors in `mpesa_callback` (log exception, return `callback_rejected`).

- [ ] **Step 4: Unique fake references for retry**

Change initiate create to:

```python
provider_reference=f'FAKE-{order.public_number}-{secrets.token_hex(4)}',
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `pytest tests/test_payment_security.py tests/test_commerce_flow.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/marketplace/payments/providers.py apps/marketplace/payments/views.py tests/test_payment_security.py
git commit -m "fix(payments): lock down fake callback and provider mismatch"
```

---

### Task 2: M-Pesa LIVE required in production + signature behavior

**Files:**
- Modify: `apps/marketplace/payments/providers.py`
- Modify: `config/settings/production.py`
- Modify: `tests/test_payment_security.py` (or extend `test_commerce_flow.py`)

**Interfaces:**
- Consumes: `MPESA_LIVE`, `MPESA_CALLBACK_SECRET`, `PAYMENT_PROVIDER`
- Produces: Production refuses mpesa without LIVE; signature required when live or secret set

- [ ] **Step 1: Write failing test for signature when secret present**

```python
@pytest.mark.django_db
@override_settings(MPESA_LIVE=False, MPESA_CALLBACK_SECRET='test-secret')
def test_mpesa_callback_rejects_unauthenticated_when_secret_configured(order_with_mpesa_pending):
    # POST without token/header → 400; payment stays pending
    ...
```

- [ ] **Step 2: Run — expect FAIL** (current code accepts when not LIVE)

- [ ] **Step 3: Fix `_verify_callback_signature`**

```python
def _verify_callback_signature(self, *, payload: dict) -> bool:
    secret = getattr(settings, 'MPESA_CALLBACK_SECRET', '') or ''
    live = getattr(settings, 'MPESA_LIVE', False)
    if live or secret:
        return bool(payload.get('callback_authenticated'))
    return True  # local scaffold without secret only
```

- [ ] **Step 4: Production settings**

In `config/settings/production.py` after existing mpesa checks:

```python
if PAYMENT_PROVIDER == 'mpesa' and not MPESA_LIVE:
    raise ImproperlyConfigured('MPESA_LIVE must be True in production.')
```

Add env-driven:

```python
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
_proxy = env.bool('DJANGO_BEHIND_PROXY', default=False)
if _proxy:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

Document both in `.env.example`.

- [ ] **Step 5: Tests + commerce suite PASS**

Run: `pytest tests/test_payment_security.py tests/test_commerce_flow.py tests/test_daraja.py -v`

- [ ] **Step 6: Commit**

```bash
git commit -m "fix(payments): require authenticated M-Pesa callbacks when secret or live"
```

---

### Task 3: Open redirect hardening

**Files:**
- Modify: `apps/accounts/views/__init__.py`
- Grep/fix other `redirect(request...next)` sites: `cart/views.py`, `favorites/views.py`, `notifications/views.py` if they redirect to user-supplied URLs
- Modify: `tests/test_accounts.py`

**Interfaces:**
- Produces: `safe_redirect_url(request, candidate, fallback)` helper (prefer in `apps/accounts/utils.py` or `apps/core/http.py`)

- [ ] **Step 1: Failing test**

```python
@pytest.mark.django_db
def test_login_rejects_open_redirect(client, user):
    # create user with known password
    resp = client.post(
        '/account/login/?next=https://evil.example/phish',
        data={'email': user.email, 'password': 'DemoPassword123!'},
    )
    assert resp.status_code in (302, 303)
    assert 'evil.example' not in resp['Location']
```

- [ ] **Step 2: Implement helper + use on login**

```python
from django.utils.http import url_has_allowed_host_and_scheme

def safe_next_url(request, candidate, fallback):
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return fallback
```

- [ ] **Step 3: Apply to all user-controlled redirects found by grep**

- [ ] **Step 4: pytest `tests/test_accounts.py` PASS + commit**

```bash
git commit -m "fix(accounts): block open redirects on login next parameter"
```

---

### Task 4: Digital asset upload validation

**Files:**
- Modify: `apps/marketplace/listings/services.py` (`add_digital_asset`)
- Create: `tests/test_digital_assets.py`

**Interfaces:**
- Mirror `orders/support.py` `_evidence_signature_matches` pattern
- Allow: `application/pdf`, `application/zip`, `image/jpeg`, `image/png`, `image/webp` (document in docstring)
- Max size: 50 * 1024 * 1024 (or product-agreed)

- [ ] **Step 1: Failing test** — upload with `content_type=application/pdf` but PNG bytes → ValidationError

- [ ] **Step 2: Implement validation in `add_digital_asset` before `DigitalAsset.objects.create`**

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "fix(listings): validate digital asset MIME and magic bytes"
```

---

### Task 5: Design-system gate + callback error hygiene already done → verify

**Files:**
- Modify: `apps/core/views/design_system.py`
- Modify: `apps/core/urls.py` if using decorator vs mixin

- [ ] **Step 1: Gate view**

```python
from django.contrib.auth.mixins import UserPassesTestMixin

class DesignSystemView(UserPassesTestMixin, TemplateView):
    template_name = 'pages/design_system.html'
    raise_exception = True

    def test_func(self):
        from django.conf import settings
        return settings.DEBUG or (self.request.user.is_authenticated and self.request.user.is_staff)
```

- [ ] **Step 2: Test anonymous production-like access → 403; DEBUG → 200**

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(core): restrict design-system page to staff or DEBUG"
```

---

### Task 6: Git init, ignore hygiene, first commit, GitHub remote

**Files:**
- Modify: `.gitignore` (add `private_media/`, `*.pem`, `.env.*` except `.env.example`)
- Create: repo git metadata
- Docs already written under `docs/superpowers/`

**Note:** If git was partially initialized earlier in this plan’s commits, skip re-init and continue.

- [ ] **Step 1: Ensure git repository**

```powershell
cd "C:\Users\Little Human\Desktop\Ziuza"
git status
# if not a repo:
git init -b main
```

- [ ] **Step 2: Expand `.gitignore`**

```
private_media/
*.pem
.env.local
.env.production
```

Keep `.env.example` tracked.

- [ ] **Step 3: Stage carefully — review `git status` for secrets**

Never add: `.env`, `db.sqlite3`, `.venv`, `media/`, `private_media/`, credentials.

- [ ] **Step 4: Initial commit if none exists**

```bash
git add -A
git status
git commit -m "chore: initial import of Ziuza marketplace"
```

If Tasks 1–5 already committed on a fresh repo, this step is “ensure history is clean”.

- [ ] **Step 5: Add remote and push**

```bash
gh repo view MukoyaKuya/Ziuza-Market-Place
# If empty / new:
git remote add origin https://github.com/MukoyaKuya/Ziuza-Market-Place.git
git push -u origin main
```

If remote has unrelated history: **stop and ask the user** — do not `--force` unless explicitly requested.

- [ ] **Step 6: Confirm**

```bash
gh repo view MukoyaKuya/Ziuza-Market-Place --web
git status -sb
```

---

### Task 7: CI + hardening docs + deploy runbook

**Files:**
- Modify: `.github/workflows/ci.yml` (optional: fail if `.env` present in tree — usually N/A)
- Modify: `docs/production-hardening.md`
- Create: `docs/deploy-runbook.md`
- Modify: `.env.example` for new settings
- Modify: `README.md` — link runbook + GitHub

- [ ] **Step 1: Correct hardening checklist**

Uncheck or rephrase payment authenticity until Tasks 1–2 merged; mark items this plan completes as done; keep Docker/Celery unchecked.

- [ ] **Step 2: Write `docs/deploy-runbook.md`** covering:

1. Required env vars (`SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PAYMENT_PROVIDER`, `MPESA_*`, `REDIS_URL`, `SENTRY_DSN`)
2. `pip install -e ".[prod]"` + migrate + `npm ci && npm run build:css` + collectstatic
3. Gunicorn: `gunicorn config.wsgi:application`
4. Cron list from README (`expire_order_reservations`, alerts, `deliver_notifications`, analytics)
5. Health: `/health/live/`, `/health/ready/`
6. Explicit: CSS must be built in deploy because `static/css/styles.css` is gitignored

- [ ] **Step 3: CI remains green**

Ensure workflow still:

```yaml
python manage.py makemigrations --check --dry-run
pytest -q
```

- [ ] **Step 4: Commit + push**

```bash
git commit -m "docs: production hardening honesty and host-agnostic deploy runbook"
git push
```

---

### Task 8: Checkout cart lock + payment confirmed uniqueness

**Files:**
- Modify: `apps/marketplace/orders/services.py`
- Modify: `apps/marketplace/payments/models.py` (+ migration)
- Create: `tests/test_checkout_integrity.py`

**Interfaces:**
- `create_checkout_order` locks cart before reading lines
- Partial UniqueConstraint: one confirmed payment per order

- [ ] **Step 1: Failing integrity tests** (double checkout / second confirm)

- [ ] **Step 2: Lock cart**

```python
@transaction.atomic
def create_checkout_order(*, actor, cart: Cart, ...):
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    totals = annotate_cart_totals(cart)
    if not totals['lines']:
        raise ValidationError(...)
    ...
```

- [ ] **Step 3: Payment model constraint**

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['order'],
            condition=models.Q(status='confirmed'),
            name='uniq_one_confirmed_payment_per_order',
        ),
    ]
```

Change `order = ForeignKey(..., on_delete=models.PROTECT)` only if no code deletes orders with payments in tests; if CASCADE is required for test teardown, keep CASCADE and document — prefer PROTECT for production integrity.

- [ ] **Step 4: `makemigrations payments` + migrate + tests PASS**

- [ ] **Step 5: Commit + push**

```bash
git commit -m "fix(orders): lock cart at checkout and unique confirmed payments"
```

---

### Task 9: Cart uniqueness + CartItem conditional constraints + inventory check

**Files:**
- Modify: `apps/marketplace/cart/models.py` (+ migration)
- Modify: `apps/marketplace/listings/models/__init__.py` Inventory Meta (+ migration)
- Modify: `apps/marketplace/cart/services.py` if get_or_create needs alignment

- [ ] **Step 1: Add constraints**

```python
# Cart
constraints = [
    models.UniqueConstraint(
        fields=['user'],
        condition=models.Q(user__isnull=False),
        name='uniq_cart_per_user',
    ),
    models.UniqueConstraint(
        fields=['session_key'],
        condition=models.Q(user__isnull=True) & ~models.Q(session_key=''),
        name='uniq_anon_cart_per_session',
    ),
]

# CartItem — replace unique_together with:
constraints = [
    models.UniqueConstraint(
        fields=['cart', 'listing', 'personalization_signature'],
        condition=models.Q(variant__isnull=True),
        name='uniq_cartitem_base_variant',
    ),
    models.UniqueConstraint(
        fields=['cart', 'listing', 'variant', 'personalization_signature'],
        condition=models.Q(variant__isnull=False),
        name='uniq_cartitem_with_variant',
    ),
]

# Inventory
models.CheckConstraint(
    check=models.Q(quantity_reserved__lte=models.F('quantity_available')),
    name='inventory_reserved_lte_available',
),
```

- [ ] **Step 2: Data migration / local cleanup if existing duplicates block migrate**

- [ ] **Step 3: Tests + commit**

```bash
git commit -m "fix(db): unique carts/items and inventory reserved check constraint"
```

---

### Task 10: Request ID + production Sentry warning

**Files:**
- Modify: `apps/core/middleware.py`
- Modify: `config/settings/base.py` (middleware order, logging filter)
- Modify: `config/settings/production.py`

- [ ] **Step 1: Add `RequestIdMiddleware`**

```python
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar('request_id', default='-')

class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        request.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response['X-Request-ID'] = rid
        return response
```

Add logging filter that injects `request_id` into records; update `LOGGING` format to include it.

Place middleware early (after SecurityMiddleware).

- [ ] **Step 2: Production Sentry warning if DSN missing**

```python
if not SENTRY_DSN:
    logging.getLogger(__name__).warning(
        'SENTRY_DSN is not set; production error tracking is disabled.'
    )
```

- [ ] **Step 3: Simple test that response includes X-Request-ID**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(observability): request ID middleware and Sentry prod warning"
```

---

### Task 11: A11y + UI quick wins

**Files:**
- Modify: `templates/layouts/base.html`
- Modify: `templates/layouts/navbar.html`
- Modify: `templates/accounts/login.html`, `templates/accounts/register.html`
- Modify: `components/listing_card/listing_card.html`
- Modify: `static/src/input.css`
- Run: `npm run build:css`
- Modify: `tests/test_design_system.py` or small template smoke tests if present

- [ ] **Step 1: Skip link** as first focusable in `base.html`:

```html
<a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:z-50 ...">Skip to content</a>
```

- [ ] **Step 2: Navbar** — bind `aria-expanded` to Alpine open state on menu/category buttons

- [ ] **Step 3: Password fields** — `type="password"` in HTML; Alpine may toggle to `text`

- [ ] **Step 4: Listing card** — remove non-functional heart **or** replace with include of `favorites/partials/button.html` when `listing_id` provided; if context lacks id, omit control

- [ ] **Step 5: CSS**

```css
.btn-outline {
  @apply inline-flex items-center justify-center rounded-ziuza border border-brand-surface-border bg-white px-4 py-2 text-sm font-semibold text-kenya-black hover:bg-brand-surface-muted;
}
```

Run `npm run build:css`.

- [ ] **Step 6: Commit**

```bash
git commit -m "fix(ui): a11y skip link, aria-expanded, btn-outline, listing card hearts"
```

---

### Task 12: Final verification + push

- [ ] **Step 1: Full test suite**

```powershell
pytest -q
python manage.py makemigrations --check --dry-run
```

Expected: all PASS; no pending migrations.

- [ ] **Step 2: Push all commits**

```bash
git push -u origin main
```

- [ ] **Step 3: Update hardening checklist final state + short note in README “Security hardening 2026-08-10”**

- [ ] **Step 4: Scorecard self-check against design table** (document in commit message or `docs/superpowers/specs/` addendum)

- [ ] **Step 5: Final commit if docs tweaked + push**

```bash
git commit -m "docs: mark security and devops-c score-lift complete"
git push
```

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| Fake callback lockdown + provider filter | 1 |
| Unique fake refs | 1 |
| MPESA_LIVE prod + signature | 2 |
| CSRF_TRUSTED_ORIGINS / proxy | 2 |
| Open redirect | 3 |
| Digital asset validation | 4 |
| Design-system gate | 5 |
| GitHub init/push | 6 |
| CI + hardening + runbook | 7 |
| Checkout lock + confirmed payment unique | 8 |
| Cart/CartItem/Inventory constraints | 9 |
| Request ID + Sentry warn | 10 |
| A11y/UI stubs | 11 |
| Final verify + push | 12 |

## Out of scope (explicit)

Docker, Celery, S3, host IaC, React, full WCAG AA, full design-system adoption pass.
