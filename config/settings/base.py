import os
from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_SETTINGS_MODULE=(str, 'config.settings.local'),
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'django-insecure-change-me-in-production'),
    ALLOWED_HOSTS=(list, ['127.0.0.1', 'localhost']),
    ORDER_RESERVATION_MINUTES=(int, 30),
    PUBLIC_SITE_URL=(str, 'http://localhost:8000'),
    DEFAULT_FROM_EMAIL=(str, 'Ziuza Marketplace <notifications@ziuza.local>'),
    EMAIL_BACKEND=(str, 'django.core.mail.backends.smtp.EmailBackend'),
    EMAIL_HOST=(str, 'localhost'),
    EMAIL_PORT=(int, 587),
    EMAIL_HOST_USER=(str, ''),
    EMAIL_HOST_PASSWORD=(str, ''),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_USE_SSL=(bool, False),
    EMAIL_TIMEOUT=(int, 15),
)

# Read .env file if present
env_file = BASE_DIR / '.env'
if env_file.exists():
    env.read_env(str(env_file))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')
PUBLIC_SITE_URL = env('PUBLIC_SITE_URL').rstrip('/')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')
EMAIL_BACKEND = env('EMAIL_BACKEND')
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = env('EMAIL_USE_TLS')
EMAIL_USE_SSL = env('EMAIL_USE_SSL')
EMAIL_TIMEOUT = env('EMAIL_TIMEOUT')

# Application definition
DJANGO_APPS = [
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = []

LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.marketplace.shops',
    'apps.marketplace.categories',
    'apps.marketplace.listings',
    'apps.marketplace.content',
    'apps.marketplace.search',
    'apps.marketplace.favorites',
    'apps.marketplace.cart',
    'apps.marketplace.orders',
    'apps.marketplace.payments',
    'apps.marketplace.shipping',
    'apps.marketplace.reviews',
    'apps.marketplace.notifications',
    'apps.marketplace.messaging',
    'apps.marketplace.analytics',
    'apps.marketplace.promotions',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.SimpleRateLimitMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # templates/ for pages & layouts; BASE_DIR so components/<name>/<name>.html resolves
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR,
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.marketplace.cart.context_processors.cart_summary',
                'apps.marketplace.notifications.context_processors.unread_notifications',
                'apps.marketplace.categories.context_processors.nav_categories',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:account_home'
LOGOUT_REDIRECT_URL = 'core:home'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

# Cache (ADR-008). LocMem by default — correctness must not require Redis.
# Production may override to Redis when REDIS_URL is set.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ziuza-default',
    }
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Payments — 'fake' (sandbox) or 'mpesa' (Daraja scaffold)
PAYMENT_PROVIDER = env('PAYMENT_PROVIDER', default='fake')
MPESA_LIVE = env.bool('MPESA_LIVE', default=False)
MPESA_DARAJA_ENABLED = env.bool('MPESA_DARAJA_ENABLED', default=False)
MPESA_CALLBACK_SECRET = env('MPESA_CALLBACK_SECRET', default='')
MPESA_CALLBACK_URL = env('MPESA_CALLBACK_URL', default='')
MPESA_CONSUMER_KEY = env('MPESA_CONSUMER_KEY', default='')
MPESA_CONSUMER_SECRET = env('MPESA_CONSUMER_SECRET', default='')
MPESA_SHORTCODE = env('MPESA_SHORTCODE', default='')
MPESA_PASSKEY = env('MPESA_PASSKEY', default='')
MPESA_TRANSACTION_TYPE = env('MPESA_TRANSACTION_TYPE', default='CustomerPayBillOnline')
MPESA_HTTP_TIMEOUT = env.int('MPESA_HTTP_TIMEOUT', default=15)
ORDER_RESERVATION_MINUTES = env('ORDER_RESERVATION_MINUTES')

# Only enable this when the application is behind a trusted proxy that replaces
# (rather than appends to) X-Forwarded-For.
TRUST_X_FORWARDED_FOR = env.bool('TRUST_X_FORWARDED_FOR', default=False)

# Optional Sentry (install sentry-sdk[django] in prod extras when enabling)
SENTRY_DSN = env('SENTRY_DSN', default='')


# Structured Logging Foundation
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Django Unfold Admin Theme Configuration
UNFOLD = {
    "SITE_TITLE": "Ziuza Marketplace Admin",
    "SITE_HEADER": "Ziuza Administration",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "232 245 233",
            "100": "200 230 201",
            "200": "165 214 167",
            "300": "129 199 132",
            "400": "102 187 106",
            "500": "76 175 80",
            "600": "0 135 81",
            "700": "0 100 58",
            "800": "0 72 43",
            "900": "0 40 24",
            "950": "0 25 15",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "User & Access Management",
                "separator": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": "admin:accounts_user_changelist",
                    },
                    {
                        "title": "Addresses",
                        "icon": "location_on",
                        "link": "admin:accounts_address_changelist",
                    },
                ],
            },
            {
                "title": "Marketplace Catalog",
                "separator": True,
                "items": [
                    {
                        "title": "Shops",
                        "icon": "store",
                        "link": "admin:shops_shop_changelist",
                    },
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": "admin:categories_category_changelist",
                    },
                    {
                        "title": "Listings",
                        "icon": "inventory_2",
                        "link": "admin:listings_listing_changelist",
                    },
                ],
            },
            {
                "title": "Orders & Commerce",
                "separator": True,
                "items": [
                    {
                        "title": "Orders",
                        "icon": "shopping_cart",
                        "link": "admin:orders_order_changelist",
                    },
                    {
                        "title": "Payments",
                        "icon": "payments",
                        "link": "admin:payments_paymenttransaction_changelist",
                    },
                    {
                        "title": "Reviews",
                        "icon": "star",
                        "link": "admin:reviews_review_changelist",
                    },
                ],
            },
        ],
    },
}
