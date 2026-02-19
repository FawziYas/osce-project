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
    ALLOWED_HOSTS=(list, ['*']),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')

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
    # Project apps
    'core.apps.CoreConfig',
    'creator.apps.CreatorConfig',
    'examiner.apps.ExaminerConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Django-axes rate limiting (must be after AuthenticationMiddleware)
    'axes.middleware.AxesMiddleware',
    # Role-based access control (must be after AuthenticationMiddleware)
    'core.middleware.RoleBasedAccessMiddleware',
    # Custom session timeout (must be after AuthenticationMiddleware)
    'core.middleware.SessionTimeoutMiddleware',
    # Custom security middleware
    'core.middleware.ContentSecurityPolicyMiddleware',
    'core.middleware.ReferrerPolicyMiddleware',
    'core.middleware.PermissionsPolicyMiddleware',
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

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session settings
# Note: Custom middleware (SessionTimeoutMiddleware) sets activity-based timeouts:
#   - Creator interface: 5 minutes from last activity
#   - Examiner interface: 5 minutes from last activity
# This setting is fallback for other paths (admin, etc.)
SESSION_COOKIE_AGE = 300  # 5 minutes fallback
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

# Lock out after 5 failed attempts
AXES_FAILURE_LIMIT = 5
# Lock out for 15 minutes
AXES_COOLOFF_TIME = timedelta(minutes=15)
# Lock based on username and IP for better security
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
# Reset attempts on successful login
AXES_RESET_ON_SUCCESS = True
# Use cache for performance
AXES_CACHE = 'default'
# Enable in admin
AXES_ENABLE_ADMIN = True
