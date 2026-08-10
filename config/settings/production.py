import logging

from .base import *

from django.core.exceptions import ImproperlyConfigured

DEBUG = False

if SECRET_KEY == 'django-insecure-change-me-in-production':
    raise ImproperlyConfigured('Production requires an explicit SECRET_KEY.')
if PAYMENT_PROVIDER == 'fake':
    raise ImproperlyConfigured('The fake payment provider cannot be used in production.')
if PAYMENT_PROVIDER == 'mpesa' and not MPESA_CALLBACK_SECRET:
    raise ImproperlyConfigured('MPESA_CALLBACK_SECRET is required for M-Pesa in production.')
if PAYMENT_PROVIDER == 'mpesa' and not MPESA_LIVE:
    raise ImproperlyConfigured('MPESA_LIVE must be True in production.')
if PAYMENT_PROVIDER == 'mpesa' and not MPESA_DARAJA_ENABLED:
    raise ImproperlyConfigured('MPESA_DARAJA_ENABLED must be true for M-Pesa in production.')
if PAYMENT_PROVIDER == 'mpesa':
    _required_mpesa = {
        'MPESA_CONSUMER_KEY': MPESA_CONSUMER_KEY,
        'MPESA_CONSUMER_SECRET': MPESA_CONSUMER_SECRET,
        'MPESA_SHORTCODE': MPESA_SHORTCODE,
        'MPESA_PASSKEY': MPESA_PASSKEY,
        'MPESA_CALLBACK_URL': MPESA_CALLBACK_URL,
    }
    _missing_mpesa = [name for name, value in _required_mpesa.items() if not value]
    if _missing_mpesa:
        raise ImproperlyConfigured(f'Missing M-Pesa settings: {", ".join(_missing_mpesa)}')
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured('EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled.')

# Production requires explicit DATABASE_URL
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Prefer Redis when REDIS_URL is configured (requires the `redis` package).
# Application correctness must not depend on cache presence (ADR-008).
_redis_url = env('REDIS_URL', default=None)
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
        }
    }

# Security Hardening
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = env.bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = env.bool('DJANGO_SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('DJANGO_CSRF_COOKIE_SECURE', default=True)
SECURE_HSTS_SECONDS = env.int('DJANGO_SECURE_HSTS_SECONDS', default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
_proxy = env.bool('DJANGO_BEHIND_PROXY', default=False)
if _proxy:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Error tracking — no-op unless SENTRY_DSN is set and sentry-sdk is installed.
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=env.float('SENTRY_TRACES_SAMPLE_RATE', default=0.0),
            send_default_pii=False,
            environment=env('SENTRY_ENVIRONMENT', default='production'),
        )
    except ImportError:
        logging.getLogger(__name__).exception('SENTRY_DSN is set but sentry-sdk is not installed')
else:
    logging.getLogger(__name__).warning(
        'SENTRY_DSN is not set; production error tracking is disabled.'
    )
