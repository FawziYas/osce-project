"""
Development settings.
"""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Use PostgreSQL if DATABASE_URL is set, otherwise fall back to SQLite
_db_url = env('DATABASE_URL', default=None)
if _db_url:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(
            _db_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', default='osce_dev'),
            'USER': env('DB_USER', default='postgres'),
            'PASSWORD': env('DB_PASSWORD', default='postgres'),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env('DB_PORT', default='5432'),
        }
    }

# Disable password validators in development
AUTH_PASSWORD_VALIDATORS = []
