from .base import *

# This module is intentionally self-contained after importing ``base``.  The
# base module reads .env for local and production settings, so every setting
# that can affect test behaviour must be pinned here.
DEBUG = False
SECRET_KEY = 'test-secret-key-for-ziuza-marketplace-testing'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = []
PUBLIC_SITE_URL = 'http://localhost:8000'
REQUIRE_EMAIL_VERIFICATION = False

DEFAULT_FROM_EMAIL = 'Ziuza Marketplace <tests@ziuza.invalid>'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
EMAIL_HOST = 'localhost'
EMAIL_PORT = 25
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 15

# File-based so pytest --reuse-db can skip the ~26s migration setup on
# subsequent runs (in-memory dies with the process). `var/` is gitignored.
TEST_DB_PATH = BASE_DIR / 'var' / 'test_ziuza.sqlite3'
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(TEST_DB_PATH),
        'TEST': {'NAME': str(TEST_DB_PATH)},
    }
}

TEST_MEDIA_ROOT = BASE_DIR / 'var' / 'test_media'
TEST_PRIVATE_MEDIA_ROOT = BASE_DIR / 'var' / 'test_private_media'
MEDIA_ROOT = TEST_MEDIA_ROOT
PRIVATE_MEDIA_ROOT = TEST_PRIVATE_MEDIA_ROOT
MEDIA_STORAGE_BACKEND = ''
MEDIA_STORAGE_OPTIONS = {}
PRIVATE_MEDIA_STORAGE_BACKEND = ''
PRIVATE_MEDIA_STORAGE_OPTIONS = {}
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {'location': str(TEST_MEDIA_ROOT), 'base_url': MEDIA_URL},
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
USE_X_ACCEL_REDIRECT = False
X_ACCEL_REDIRECT_PREFIX = '/protected_media/'

PAYMENT_PROVIDER = 'fake'
MPESA_LIVE = False
MPESA_DARAJA_ENABLED = False
MPESA_CALLBACK_SECRET = ''
MPESA_CALLBACK_URL = ''
MPESA_CONSUMER_KEY = ''
MPESA_CONSUMER_SECRET = ''
MPESA_SHORTCODE = ''
MPESA_PASSKEY = ''
MPESA_TRANSACTION_TYPE = 'CustomerPayBillOnline'
MPESA_HTTP_TIMEOUT = 15
ORDER_RESERVATION_MINUTES = 30
WHATSAPP_CHECKOUT_ENABLED = True
WHATSAPP_ORDER_RESERVATION_HOURS = 24
TRUSTED_PROXY_IPS = []
TRUSTED_CLIENT_IP_HEADER = ''
SENTRY_DSN = ''

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Celery test configuration - run tasks synchronously in memory
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
