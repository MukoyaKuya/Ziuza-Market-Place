"""Hardened settings for the single-machine Cloudflare Tunnel deployment."""

from .production import *

ALLOWED_HOSTS = ['ziuza.shop', 'www.ziuza.shop', 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = ['https://ziuza.shop', 'https://www.ziuza.shop']
PUBLIC_SITE_URL = 'https://ziuza.shop'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
TRUSTED_PROXY_IPS = ['127.0.0.1', '::1']
TRUSTED_CLIENT_IP_HEADER = 'HTTP_CF_CONNECTING_IP'

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STORAGES['staticfiles'] = {
    # The source Tailwind file is deliberately present under static/src.  It
    # contains an ``@import "tailwindcss"`` directive that must not be
    # rewritten as an asset URL, so use WhiteNoise's plain static storage for
    # this single-machine profile.
    'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
}
