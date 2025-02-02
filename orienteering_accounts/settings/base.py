"""
Django settings for liber_marketplace_connector project.

Generated by 'django-admin startproject' using Django 2.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
from datetime import timedelta
from decouple import AutoConfig, Csv

config = AutoConfig(os.environ.get('DJANGO_CONFIG_ENV_DIR'))

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_DIR = config('PROJECT_APP_DIR', default='')

PROJECT_NAME = config('PROJECT_NAME', default='orienteering_accounts')

PROJECT_DOMAIN = config('PROJECT_MAIN_DOMAIN', default='')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('PROJECT_SECRET_KEY', default='')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

DEBUG_STATIC_FILES = False

ALLOWED_HOSTS = config('PROJECT_ALLOWED_HOSTS', cast=Csv(), default='')

ADMINS = [(email, email) for email in config('PROJECT_ADMINS', default='', cast=Csv())]

SERVER_EMAIL = config('PROJECT_SERVER_EMAIL', default='')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'django_extensions',

    'orienteering_accounts',
    'orienteering_accounts.core',
    'orienteering_accounts.account',
    'orienteering_accounts.event',
    'orienteering_accounts.entry',
    'anymail',
    "crispy_forms",
    "crispy_bootstrap5"
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'orienteering_accounts.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
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

WSGI_APPLICATION = 'orienteering_accounts.wsgi.application'

ENVIRONMENT = config('PROJECT_ENVIRONMENT_TYPE', default='')

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRESQL_DATABASE', default='postgres'),
        'USER': config('POSTGRESQL_USER', default='postgres'),
        'HOST': config('POSTGRESQL_HOST', default='db'),
        'PORT': config('POSTGRESQL_PORT', default='5432'),
        'PASSWORD': config('POSTGRESQL_PASSWORD', default=''),
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 600,
    }
}

# Redis
REDIS_LOCATION = config('PROJECT_REDIS_LOCATION', default='redis://redis:6379')
# REDIS_DATABASE_NUMBER_OFFSET+0 is saved for celery
# Marketplace connector reserved databases <REDIS_DATABASE_NUMBER_OFFSET, REDIS_DATABASE_NUMBER_OFFSET+19>
REDIS_DATABASE_NUMBER_OFFSET = config('PROJECT_REDIS_DATABASE_NUMBER_OFFSET', default=0, cast=int)

# Caches

MARKETPLACE_CACHE = 'marketplace'
MARKETPLACE_REDIS_DB_NUMBER = REDIS_DATABASE_NUMBER_OFFSET + 2
LISTING_RESULTS_CACHE = 'feed_results'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_LOCATION,
        'TIMEOUT': None,
        'OPTIONS': {
            'DB': REDIS_DATABASE_NUMBER_OFFSET + 1,
            'PASSWORD': '',
            'PARSER_CLASS': 'redis.connection.DefaultParser',
        },
        'KEY_PREFIX': config('PROJECT_ENVIRONMENT_TYPE', default='')
    }
}

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'cs'

TIME_ZONE = 'Europe/Prague'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOCALE_PATHS = [config('PROJECT_LOCALE_PATHS', default=os.path.join(APP_DIR, 'locale'))]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/
STATIC_ROOT = config('PROJECT_STATIC_ROOT', default=os.path.join(BASE_DIR, "static"))

STATIC_URL = '/static/'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

MEDIA_ROOT = config('PROJECT_MEDIA_ROOT', default=os.path.join(BASE_DIR, "media"))

MEDIA_URL = '/media/'


###########
# LOGGING #
###########

LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(processName)s (%(process)d) %(threadName)s (%(thread)d) <%(name)s> %(message)s'
        },
        'plain': {
            'format': '%(asctime)s %(levelname)s <%(name)s> %(message)s'
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'file_debug': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'verbose',
        },
        'file_info': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'info.log',
            'formatter': 'verbose',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': 'error.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'plain',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file_debug', 'file_info', 'file_error', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'orienteering_accounts': {
            'handlers': ['file_debug', 'file_info', 'file_error', 'mail_admins'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

###########
# EMAILS #
###########

EMAIL_BACKEND = "anymail.backends.mailjet.EmailBackend"

ANYMAIL = {
    "MAILJET_API_KEY": config('PROJECT_MAILJET_API_KEY', default=''),
    "MAILJET_SECRET_KEY": config("PROJECT_MAILJET_SECRET_KEY", default='')
}

DEFAULT_FROM_EMAIL = config('PROJECT_DEFAULT_FROM_EMAIL', default='')

# Project

AUTH_USER_MODEL = 'account.Account'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

CLUB_KEY = config('PROJECT_CLUB_KEY', '')
CLUB_ID = config('PROJECT_CLUB_ID', '')

ORIS_SOURCE_TYPE_BULLETIN_ID = '1'

ORIS_API_URL = config('PROJECT_ORIS_API_URL', '')
ORIS_API_USERNAME = config('PROJECT_ORIS_API_USERNAME', '')
ORIS_API_PASSWORD = config('PROJECT_ORIS_API_PASSWORD', '')

REFRESH_EVENTS_BEFORE_DAYS = 14

TEMPLATE_DATETIME_FORMAT = '%d.%m.%Y %H:%M'
TEMPLATE_DATE_FORMAT = '%d.%m.%Y'

X_FRAME_OPTIONS = 'ALLOWALL'

API_SECRET = config('PROJECT_API_SECRET', '')

EVENT_PAYMENT_EMAILS_SEND_TO = config('PROJECT_EVENT_PAYMENT_EMAILS_SEND_TO', default='', cast=Csv())
ACCOUNT_CREATED_EMAILS_SEND_TO = config('PROJECT_ACCOUNT_CREATED_EMAILS_SEND_TO', default='', cast=Csv())

CLUB_BANK_ACCOUNT_NUMBER = config('PROJECT_CLUB_BANK_ACCOUNT_NUMBER', '')
CLUB_BANK_CODE = config('PROJECT_CLUB_BANK_CODE', '')

ORIS_STAGE_RACE_ID = 13
ORIS_RELAY_RACE_IDS = [5, 6, 15]

GOOGLE_SERVICE_ACCOUNT_CREDENTIALS = config('PROJECT_GOOGLE_SERVICE_ACCOUNT_CREDENTIALS', '')
GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_SUBJECT = config('PROJECT_GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_SUBJECT', '')

GOOGLE_GROUP_MEMBERS = 'clenove@skob-zlin.cz'
GOOGLE_GROUP_ENTRIES = 'prihlasky@skob-zlin.cz'
GOOGLE_GROUP_INFO = 'info@skob-zlin.cz'
GOOGLE_GROUP_TRAINERS = 'treneri@skob-zlin.cz'

RB_API_URL = 'https://api.rb.cz/rbcz/premium/api'
RB_API_CLIENT_ID = config('PROJECT_RB_API_CLIENT_ID', '')
RB_API_P12_CERT_PASSWORD = config('PROJECT_RB_API_P12_CERT_PASSWORD', '')
RB_API_P12_CERT_PATH = config('PROJECT_RB_API_P12_CERT_PATH', '')

LAST_BANK_TRANSACTION_READ_CACHE_KEY_PATTERN = 'last_bank_transaction_read:{bank_account_number}'
