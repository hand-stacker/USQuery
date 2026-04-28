from gqlauth.settings_type import GqlAuthSettings
from datetime import timedelta
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv('.env.local')
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).resolve().parent.parent
CONGRESS_DIR = 'https://api.congress.gov/v3/'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')
PROMPT = os.environ.get('PROMPT')
COLUMN_LIST = os.environ.get("COLUMN_LIST").split(',')
CONGRESS_KEY = os.environ.get('CONGRESS_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_IDS = os.environ.get('GOOGLE_CLIENT_IDS')
GOOGLE_WEB_CLIENT_ID = os.environ.get('GOOGLE_WEB_CLIENT_ID')
APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID')
SUBSCRIPTIONS_ENABLED = os.environ.get('SUBSCRIPTIONS_ENABLED', 'false').lower() == 'true'

# Allow Google Sign-In popup (gsi/transform) to postMessage back via window.opener.
# Django 4.1+ defaults to 'same-origin' which nulls window.opener in popups.
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PLUS_PRICE_ID = os.environ.get('STRIPE_PLUS_PRICE_ID')
STRIPE_PREMIUM_PRICE_ID = os.environ.get('STRIPE_PREMIUM_PRICE_ID')
STRIPE_PLUS_DISPLAY_PRICE = os.environ.get('STRIPE_PLUS_DISPLAY_PRICE', '$2.99/mo')
STRIPE_PREMIUM_DISPLAY_PRICE = os.environ.get('STRIPE_PREMIUM_DISPLAY_PRICE', '$14.99/mo')

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
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

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