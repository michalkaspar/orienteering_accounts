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

PROJECT_NAME = config('PROJECT_NAME', default='orienteering_accounts')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('PROJECT_SECRET_KEY', default='')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('PROJECT_DEBUG', default=True)

DEBUG_STATIC_FILES = False

ALLOWED_HOSTS = config('PROJECT_ALLOWED_HOSTS', cast=Csv(), default='')


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
    'orienteering_accounts.entry'
]

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
        'TIMEOUT': 0,
        'OPTIONS': {
            'DB': REDIS_DATABASE_NUMBER_OFFSET + 1,
            'PASSWORD': '',
            'PARSER_CLASS': 'redis.connection.HiredisParser'
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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Prague'

USE_I18N = True

USE_L10N = True

USE_TZ = True


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
        }
    },
    'loggers': {
        'project': {
            'handlers': ['file_debug', 'file_info', 'file_error'],
            'level': 'DEBUG',
        },
    },
}

# Project

AUTH_USER_MODEL = 'account.Account'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

CLUB_KEY = config('PROJECT_CLUB_KEY', '')
CLUB_ID = config('PROJECT_CLUB_ID', '')

ORIS_API_URL = config('PROJECT_ORIS_API_URL', '')

REFRESH_EVENTS_BEFORE_DAYS = 14

TEMPLATE_DATETIME_FORMAT = '%d.%m.%Y %H:%M'
TEMPLATE_DATE_FORMAT = '%d.%m.%Y'

X_FRAME_OPTIONS = 'ALLOWALL'
