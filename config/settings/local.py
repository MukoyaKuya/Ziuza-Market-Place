from .base import *

DEBUG = True

# Database logic: Use DATABASE_URL if available, else SQLite fallback for local dev
if env('DATABASE_URL', default=None):
    DATABASES = {
        'default': env.db('DATABASE_URL')
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Email: print to the runserver console until SMTP credentials exist in .env.
# (Resend is prewired in .env — pasting the API key is enough to go live.)
if not env('EMAIL_HOST_PASSWORD', default=''):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8007',
    'http://127.0.0.1:8007',
    'https://*.trycloudflare.com',
]
