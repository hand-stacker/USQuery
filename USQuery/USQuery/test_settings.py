"""Settings for the pytest suite.

USQuery/settings.py reads .env.local, whose DATABASE_URL is the production
Render Postgres, whose REDIS_URL is the production cache, and whose SMTP
settings send real email. This module makes sure none of that is reachable
from a test run, locally or in CI:

1. dotenv.load_dotenv is replaced with a no-op *before* settings.py imports
   it, so .env.local is never read. Local runs then behave exactly like CI,
   where the file doesn't exist.
2. Every env var settings.py reads is given a harmless stub (some of them are
   .split() at import time and crash on None).
3. DATABASES, CACHES and EMAIL_BACKEND are re-assigned explicitly after the
   star-import.

conftest.py additionally aborts the session if the resolved database is not
the disposable test container.
"""

import os

import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

TEST_DATABASE_URL = os.environ.get(
    'TEST_DATABASE_URL',
    'postgresql://postgres:test@localhost:5433/usquery_test',
)

_STUB_ENV = {
    'SECRET_KEY': 'test-secret-key-not-for-production',
    'PROMPT': 'test prompt',
    'ALLOWED_HOSTS': 'testserver,localhost,127.0.0.1',
    'DATABASE_URL': TEST_DATABASE_URL,
    'REDIS_URL': 'redis://localhost:6399/0',
    'DEBUG': 'false',
    'CONGRESS_KEY': 'test-congress-key',
    'GEMINI_KEY': 'test-gemini-key',
    'ANTHROPIC_API_KEY': 'test-anthropic-key',
    'VOYAGE_API_KEY': 'test-voyage-key',
    'BREVO_USER': 'test-brevo-user',
    'BREVO_API_KEY': 'test-brevo-key',
    'GOOGLE_CLIENT_ID': 'test-google-client-id',
    'GOOGLE_CLIENT_IDS': 'test-google-client-id',
    'GOOGLE_WEB_CLIENT_ID': 'test-google-web-client-id',
    'APPLE_CLIENT_ID': 'com.usquery.test',
    'APPLE_BUNDLE_ID': 'com.usquery.mycongress',
    'SUBSCRIPTIONS_ENABLED': 'true',
    'STRIPE_TEST': 'false',
    'STRIPE_SECRET_KEY': 'sk_test_stub',
    'STRIPE_PUBLISHABLE_KEY': 'pk_test_stub',
    'STRIPE_WEBHOOK_SECRET': 'whsec_stub',
    'STRIPE_PLUS_PRICE_ID': 'price_plus_test',
    'STRIPE_PLUS_PRO_PRICE_ID': 'price_plus_pro_test',
    'STRIPE_PREMIUM_PRICE_ID': 'price_premium_test',
    'APPLE_IAP_ALLOW_SANDBOX': 'false',
}

# Forced, not setdefault: a developer shell or CI runner that happens to export
# a real DATABASE_URL / REDIS_URL / API key must not leak into the test run.
os.environ.update(_STUB_ENV)

from USQuery.settings import *  # noqa: E402,F401,F403

import dj_database_url  # noqa: E402

DATABASES = {'default': dj_database_url.parse(TEST_DATABASE_URL)}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'usquery-tests',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

DEBUG = False

# settings.py selects ManifestStaticFilesStorage when DEBUG is off, which
# raises on {% static %} unless collectstatic has run.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null'], 'level': 'CRITICAL'},
}
