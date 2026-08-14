from .base import *

DEBUG = False
SECRET_KEY = 'test-secret-key-for-ziuza-marketplace-testing'

# Tests must be hermetic — never inherit PUBLIC_SITE_URL (or other env)
# from a developer's .env file.
PUBLIC_SITE_URL = 'http://localhost:8000'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
 
# Celery test configuration - run tasks synchronously in memory
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
