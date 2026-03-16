"""
Production settings — best-practice configuration.
Reads all secrets from environment variables.
"""
import os
import sentry_sdk
from .base import *   # noqa: F401,F403

# ──────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────
DEBUG = False

SECRET_KEY = env('SECRET_KEY')  # REQUIRED — no default
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# ──────────────────────────────────────────────────────────────
# Database — PostgreSQL with connection pooling
# ──────────────────────────────────────────────────────────────
import dj_database_url  # noqa: E402

# Prefer DATABASE_URL (Railway, Render, Azure) or individual vars.
# For Azure PostgreSQL Flexible Server with PgBouncer use port 6432 and
# append ?sslmode=require to the URL, e.g.:
#   postgresql://osce_app:PASSWORD@server.postgres.database.azure.com:6432/osce_production?sslmode=require
_db_url = env('DATABASE_URL', default=None)
if _db_url:
    DATABASES = {
        'default': dj_database_url.parse(
            _db_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Individual variable fallback — also supports DB_SSLMODE env var
    _db_sslmode = env('DB_SSLMODE', default='require')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', default='osce_prod'),
            'USER': env('DB_USER', default='osce'),
            'PASSWORD': env('DB_PASSWORD'),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env('DB_PORT', default='5432'),
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'connect_timeout': 10,
                'sslmode': _db_sslmode,
            },
        }
    }

# ──────────────────────────────────────────────────────────────
# Static files — WhiteNoise (compressed + hashed filenames)
# ──────────────────────────────────────────────────────────────
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# ──────────────────────────────────────────────────────────────
# Redis cache (optional — falls back to local memory if not set)
# ──────────────────────────────────────────────────────────────
_redis_url = env('REDIS_URL', default=None)
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _redis_url,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'TIMEOUT': 300,
        }
    }
    # Use Redis for sessions when Redis is available
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# ──────────────────────────────────────────────────────────────
# Security — HTTPS & cookie hardening
# ──────────────────────────────────────────────────────────────
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000        # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# ──────────────────────────────────────────────────────────────
# Password validation — stricter in production
# ──────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ──────────────────────────────────────────────────────────────
# Logging — rotating file handlers for production
# ──────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'production': {
            'format': '[{asctime}] {levelname} {name} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'production',
        },
        'audit_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'audit.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'production',
            'encoding': 'utf-8',
        },
        'auth_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'auth.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'production',
            'encoding': 'utf-8',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'error.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'production',
            'encoding': 'utf-8',
            'level': 'ERROR',
        },
    },
    'loggers': {
        'osce.audit': {
            'handlers': ['console', 'audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'osce.auth': {
            'handlers': ['console', 'auth_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console', 'error_file'],
            'level': 'WARNING',
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ──────────────────────────────────────────────────────────────
# Sentry error tracking (optional — set SENTRY_DSN env var)
# ──────────────────────────────────────────────────────────────
_sentry_dsn = env('SENTRY_DSN', default=None)
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1,   # 10% of requests for performance
        profiles_sample_rate=0.1,
        send_default_pii=False,   # Don't send PII to Sentry
        environment='production',
    )
