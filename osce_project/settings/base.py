"""
Base Django settings for osce_project.
Common settings shared between development and production.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path
import environ

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Check if running tests
TESTING = 'test' in sys.argv

# Environment variables
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
# A dev-only fallback is provided so local runs work without a .env file.
# production.py overrides this with a strict env('SECRET_KEY') — no default.
SECRET_KEY = env('SECRET_KEY', default='django-insecure-dev-only-change-in-production')

# Secret admin URL path — scanners probing /admin/ get a 404
# Change SECRET_ADMIN_URL in .env to rotate the admin URL with no code changes
SECRET_ADMIN_URL = env('SECRET_ADMIN_URL', default='manage-osce-exam-77x')

# Default password for every newly-created user (overridden on first login)
DEFAULT_USER_PASSWORD = env('DEFAULT_USER_PASSWORD', default='12345678F')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'axes',
    'rest_framework',
    # Project apps
    'core.apps.CoreConfig',
    'creator.apps.CreatorConfig',
    'examiner.apps.ExaminerConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # Serve static files efficiently
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Admin double-lock: blocks /admin/ entirely, gates secret URL with session token
    'core.middleware.AdminAccessMiddleware',
    # Django-axes rate limiting (must be after AuthenticationMiddleware)
    'axes.middleware.AxesMiddleware',
    # Force password change for users with default password
    'core.middleware.ForcePasswordChangeMiddleware',
    # Role-based access control (must be after AuthenticationMiddleware)
    'core.middleware.RoleBasedAccessMiddleware',
    # Audit log 401/403/404 responses
    'core.middleware.UnauthorizedAccessMiddleware',
    # Custom session timeout (must be after AuthenticationMiddleware)
    'core.middleware.SessionTimeoutMiddleware',
    # PostgreSQL Row-Level Security session variables (no-op on SQLite)
    'core.middleware.RLSSessionMiddleware',
    # Custom security middleware
    'core.middleware.ContentSecurityPolicyMiddleware',
    'core.middleware.ReferrerPolicyMiddleware',
    'core.middleware.PermissionsPolicyMiddleware',
    # Block search engine indexing (X-Robots-Tag on all responses)
    'core.middleware.SearchEngineBlockingMiddleware',
]

ROOT_URLCONF = 'osce_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.admin_token',
            ],
        },
    },
]

WSGI_APPLICATION = 'osce_project.wsgi.application'

# Custom user model
AUTH_USER_MODEL = 'core.Examiner'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Login URL
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/examiner/home/'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Media files (user uploads — question images, etc.)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.api.exceptions.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': None,
    'UNAUTHENTICATED_USER': None,
}

# Session settings
# Note: Custom middleware (SessionTimeoutMiddleware) sets activity-based timeouts:
#   - Creator interface (admin/coordinator/superuser): 10 minutes from last activity
#   - Examiner interface: 20 minutes from last activity
# This setting is fallback for other paths (admin, etc.)
SESSION_COOKIE_AGE = 1200  # 20 minutes fallback
SESSION_SAVE_EVERY_REQUEST = True  # Slide expiry on every request (activity-based)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ==========================================================================
# OSCE SETTINGS
# ==========================================================================
DEFAULT_ROTATION_MINUTES = 8
AUTOSAVE_INTERVAL = 30
MAX_OFFLINE_QUEUE = 100

ILO_THEMES = {
    1: {'name': 'Medical Knowledge', 'color': '#6f42c1', 'icon': 'bi-book-half'},
    2: {'name': 'Diagnosis', 'color': '#0d6efd', 'icon': 'bi-clipboard2-pulse'},
    3: {'name': 'Management', 'color': '#198754', 'icon': 'bi-prescription2'},
    4: {'name': 'Health Systems', 'color': '#fd7e14', 'icon': 'bi-hospital'},
    5: {'name': 'Communication', 'color': '#20c997', 'icon': 'bi-chat-heart'},
    6: {'name': 'Professionalism', 'color': '#dc3545', 'icon': 'bi-award'},
}

# ==========================================================================
# DJANGO-AXES RATE LIMITING
# ==========================================================================

# ==========================================================================
# TRUSTED PROXIES (for X-Forwarded-For IP extraction)
# ==========================================================================
# Add your reverse-proxy IPs here in production (e.g. ['127.0.0.1', '10.0.0.1'])
# If empty, X-Forwarded-For is trusted from any source (dev convenience).
TRUSTED_PROXIES = env.list('TRUSTED_PROXIES', default=[])

# ==========================================================================
# CELERY (async task queue for audit logging)
# ==========================================================================
# Set CELERY_BROKER_URL in .env to enable async audit writes.
# When unset, audit logs are written synchronously (safe fallback).
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # seconds (5 min; PDF/bulk tasks need headroom)
CELERY_BEAT_SCHEDULE = {
    'compute-dashboard-stats': {
        'task': 'core.compute_dashboard_stats',
        'schedule': 300,  # every 5 minutes
    },
    'cleanup-audit-logs': {
        'task': 'core.cleanup_old_audit_logs',
        'schedule': 86400,  # every 24 hours (nightly)
        'kwargs': {'days': 365},
    },
}

# ==========================================================================
# AUDIT LOGGING
# ==========================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'audit': {
            'format': '[{asctime}] {levelname} {name} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'audit',
        },
        'audit_file': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'audit.log'),
            'formatter': 'audit',
            'encoding': 'utf-8',
        },
        'auth_file': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'auth.log'),
            'formatter': 'audit',
            'encoding': 'utf-8',
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
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}
if TESTING:
    # Don't use axes in tests (it requires request object)
    AUTHENTICATION_BACKENDS = [
        'django.contrib.auth.backends.ModelBackend',
    ]
else:
    AUTHENTICATION_BACKENDS = [
        'axes.backends.AxesBackend',  # AxesBackend with ModelBackend fallback
        'django.contrib.auth.backends.ModelBackend',
    ]

# Lock out after 10 failed attempts
AXES_FAILURE_LIMIT = 10
# Lock out for 10 minutes
AXES_COOLOFF_TIME = timedelta(minutes=10)
# Lock based on username only so devices sharing the same public IP
# (e.g. same WiFi) don't affect each other for different accounts
AXES_LOCKOUT_PARAMETERS = ['username']
# Reset attempts on successful login
AXES_RESET_ON_SUCCESS = True
# Use cache for performance
AXES_CACHE = 'default'
# Enable in admin
AXES_ENABLE_ADMIN = True
# Enable access failure logging
AXES_ENABLE_ACCESS_FAILURE_LOG = True
