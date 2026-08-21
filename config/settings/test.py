from .base import *

DEBUG = False
SECRET_KEY = 'test-secret-key-for-ziuza-marketplace-testing'

# Tests must be hermetic — never inherit PUBLIC_SITE_URL (or other env)
# from a developer's .env file.
PUBLIC_SITE_URL = 'http://localhost:8000'

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

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Celery test configuration - run tasks synchronously in memory
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
