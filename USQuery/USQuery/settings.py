from gqlauth.settings_type import GqlAuthSettings
from datetime import timedelta
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Local dev only: no-op where the file doesn't exist (Docker injects env_file,
# Render injects environment variables), and never overrides a real env var.
load_dotenv('.env.local')
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).resolve().parent.parent
CONGRESS_DIR = 'https://api.congress.gov/v3/'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')


def _secretss_prompt():
    # Fallback for deployments that ship the prompt as a secretss.py module
    # (a Render secret file) instead of the PROMPT environment variable.
    try:
        import secretss
        return secretss.prompt
    except (ImportError, AttributeError):
        return None


PROMPT = os.environ.get('PROMPT') or _secretss_prompt()
CONGRESS_KEY = os.environ.get('CONGRESS_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
VOYAGE_API_KEY=os.environ.get('VOYAGE_API_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_IDS = os.environ.get('GOOGLE_CLIENT_IDS')
GOOGLE_WEB_CLIENT_ID = os.environ.get('GOOGLE_WEB_CLIENT_ID')
APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID')
APPLE_BUNDLE_ID = os.environ.get('APPLE_BUNDLE_ID')
SUBSCRIPTIONS_ENABLED = os.environ.get('SUBSCRIPTIONS_ENABLED', 'false').lower() == 'true'

# Allow Google Sign-In popup (gsi/transform) to postMessage back via window.opener.
# Django 4.1+ defaults to 'same-origin' which nulls window.opener in popups.
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PLUS_PRICE_ID = os.environ.get('STRIPE_PLUS_PRICE_ID')
STRIPE_PLUS_PRO_PRICE_ID = os.environ.get('STRIPE_PLUS_PRO_PRICE_ID')
STRIPE_PREMIUM_PRICE_ID = os.environ.get('STRIPE_PREMIUM_PRICE_ID')
STRIPE_PLUS_DISPLAY_PRICE = os.environ.get('STRIPE_PLUS_DISPLAY_PRICE', '$2.99/mo')
STRIPE_PLUS_PRO_DISPLAY_PRICE = os.environ.get('STRIPE_PLUS_PRO_DISPLAY_PRICE', '$7.99/mo')
STRIPE_PREMIUM_DISPLAY_PRICE = os.environ.get('STRIPE_PREMIUM_DISPLAY_PRICE', '$19.99/mo')

# for internal testing:
STRIPE_TEST = os.environ.get('STRIPE_TEST', 'false').lower() == 'true'

if STRIPE_TEST:
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY_TEST')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY_TEST')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET_TEST')
    STRIPE_PLUS_PRICE_ID = os.environ.get('STRIPE_PLUS_PRICE_ID_TEST')
    STRIPE_PLUS_PRO_PRICE_ID = os.environ.get('STRIPE_PLUS_PRO_PRICE_ID_TEST')
    STRIPE_PREMIUM_PRICE_ID = os.environ.get('STRIPE_PREMIUM_PRICE_ID_TEST')
    STRIPE_PLUS_DISPLAY_PRICE = os.environ.get('STRIPE_PLUS_DISPLAY_PRICE_TEST', '$2.99/mo')
    STRIPE_PLUS_PRO_DISPLAY_PRICE = os.environ.get('STRIPE_PLUS_PRO_DISPLAY_PRICE_TEST', '$7.99/mo')
    STRIPE_PREMIUM_DISPLAY_PRICE = os.environ.get('STRIPE_PREMIUM_DISPLAY_PRICE_TEST', '$19.99/mo')

# Apple In-App Purchase (StoreKit 2). iOS cannot use Stripe for subscriptions
# (App Store guideline 3.1.1), so every iOS purchase goes through StoreKit and is
# verified server-side against Apple's signed payloads.
# Defaults to the Sign in with Apple bundle id -- it is the same app.
APPLE_IAP_BUNDLE_ID = os.environ.get('APPLE_IAP_BUNDLE_ID') or APPLE_BUNDLE_ID
# Numeric App Store app id. Required by SignedDataVerifier for Production.
APPLE_IAP_APP_APPLE_ID = os.environ.get('APPLE_IAP_APP_APPLE_ID')
# App Store Server API credentials (App Store Connect -> Users and Access ->
# Integrations -> In-App Purchase). Used to fetch authoritative subscription
# state on verify/restore and to reconcile notifications we never received.
APPLE_IAP_ISSUER_ID = os.environ.get('APPLE_IAP_ISSUER_ID')
APPLE_IAP_KEY_ID = os.environ.get('APPLE_IAP_KEY_ID')
# The .p8 private key. Docker injects config through env_file only (no secrets
# mount), so the PEM is passed inline with escaped newlines; the file path is
# the local-dev alternative.
APPLE_IAP_PRIVATE_KEY = (os.environ.get('APPLE_IAP_PRIVATE_KEY') or '').replace('\\n', '\n')
APPLE_IAP_PRIVATE_KEY_PATH = os.environ.get('APPLE_IAP_PRIVATE_KEY_PATH')
# Sandbox transactions (TestFlight, sandbox testers) are rejected unless this is
# on, so a sandbox Apple ID can't mint itself a paid tier on the live backend.
APPLE_IAP_ALLOW_SANDBOX = os.environ.get('APPLE_IAP_ALLOW_SANDBOX', 'false').lower() == 'true'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS').split(',')
 
# Application references
# https://docs.djangoproject.com/en/2.1/ref/settings/#std:setting-INSTALLED_APPS
INSTALLED_APPS = [
    'app',
    'SenateQuery',
    'BillQuery',
    'strawberryAPI',
    'notifications',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admindocs',
    'django.contrib.postgres',
    'django_select2',
    'aiohttp',
    'dj_database_url',
    'google',
    'bs4',
    'rest_framework',
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    'strawberry.django',
    'rest_framework_simplejwt',
    'gqlauth'
]

# Middleware framework
# https://docs.djangoproject.com/en/2.1/topics/http/middleware/
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'gqlauth.core.middlewares.django_jwt_middleware'
]

ROOT_URLCONF = 'USQuery.urls'

# Template configuration
# https://docs.djangoproject.com/en/2.1/topics/templates/
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'USQuery.wsgi.application'
# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
 
database_url = os.environ.get('DATABASE_URL')
DATABASES['default'] = dj_database_url.parse(database_url)

# Urls for models
ABSOLUTE_URL_OVERRIDES = {
    'senatequery.models.senator': lambda o: "senate-query/search/%s/" % o.id,
}
# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Auth settings for graphql
GQL_AUTH = GqlAuthSettings(
    LOGIN_REQUIRE_CAPTCHA=False,
    REGISTER_REQUIRE_CAPTCHA=False,
)

# SMTP settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp-relay.brevo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("BREVO_USER")
EMAIL_HOST_PASSWORD = os.environ.get("BREVO_API_KEY")
DEFAULT_FROM_EMAIL = "USQuery <no-reply@usquery.com>"

AUTHENTICATION_BACKENDS = [
    "app.auth_backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Auth config
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
# Where collectstatic writes and urls.py serves from, relative to BASE_DIR (or
# absolute). Build output only -- never committed (see .gitignore).
STATIC_ROOT = os.path.join(BASE_DIR, os.environ.get('STATIC_ROOT_DIR', 'staticfiles'))
# Outside DEBUG, collectstatic writes content-hashed copies (site.3f9a1c.css) and
# {% static %} emits those names, so a CDN (Cloudflare) can never serve a stale
# file after a deploy. STORAGES, not the old STATICFILES_STORAGE setting, which
# Django 5.1 removed and silently ignores.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
            else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        ),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SSL": True,
        }
    }
}