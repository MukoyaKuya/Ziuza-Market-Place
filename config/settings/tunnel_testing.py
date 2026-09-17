"""Temporary public testing profile for a Cloudflare Tunnel development host.

This intentionally permits SQLite and fake payments. Do not use it for real
orders or sensitive production data; use ``config.settings.selfhost`` instead.
"""

from .local import *

# Public preview must not run with local DEBUG / open hosts.
DEBUG = False

ALLOWED_HOSTS = ['ziuza.shop', 'www.ziuza.shop', 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = ['https://ziuza.shop', 'https://www.ziuza.shop']
PUBLIC_SITE_URL = 'https://ziuza.shop'
REQUIRE_EMAIL_VERIFICATION = False
PUBLIC_PREVIEW_MODE = True

# Cloudflare Tunnel terminates TLS in front of Waitress on localhost.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Keep False at the origin so local health checks on http://127.0.0.1 stay simple;
# Cloudflare should still force HTTPS at the edge.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STORAGES['staticfiles'] = {
    'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
}