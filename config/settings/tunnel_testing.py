"""Temporary public testing profile for a Cloudflare Tunnel development host.

This intentionally permits SQLite and fake payments. Do not use it for real
orders or sensitive production data; use ``config.settings.selfhost`` instead.
"""

from .local import *

ALLOWED_HOSTS = ['ziuza.shop', 'www.ziuza.shop', 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = ['https://ziuza.shop', 'https://www.ziuza.shop']
REQUIRE_EMAIL_VERIFICATION = False
