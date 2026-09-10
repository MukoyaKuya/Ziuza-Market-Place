"""PostgreSQL-only settings for transaction and row-lock integration tests.

The values deliberately match the disposable PostgreSQL service in CI. Normal
tests continue to use ``config.settings.test`` and never depend on a database
server or values from a developer's environment.
"""

from .test import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ziuza_test',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}
