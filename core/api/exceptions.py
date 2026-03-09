"""
Custom DRF exception handler — uniform error envelope.

Every error response follows:
{
    "error": "Human-readable message",
    "code":  "MACHINE_CODE",
    "detail": "Extra context or null"
}
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
)
from django.http import Http404


# ── Error codes ──────────────────────────────────────────────────────
NOT_AUTHENTICATED = 'NOT_AUTHENTICATED'
AUTHENTICATION_FAILED = 'AUTHENTICATION_FAILED'
PERMISSION_DENIED = 'PERMISSION_DENIED'
NOT_FOUND = 'NOT_FOUND'
VALIDATION_ERROR = 'VALIDATION_ERROR'
SESSION_NOT_ACTIVE = 'SESSION_NOT_ACTIVE'
SCORE_FINALIZED = 'SCORE_FINALIZED'
SERVER_ERROR = 'SERVER_ERROR'


def custom_exception_handler(exc, context):
    """
    Override DRF's default exception handler to produce a consistent
    error envelope across all endpoints.
    """
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — let Django's 500 handler deal with it
        return None

    # Build the uniform envelope
    if isinstance(exc, NotAuthenticated):
        body = {
            'error': 'Authentication credentials were not provided.',
            'code': NOT_AUTHENTICATED,
            'detail': None,
        }
    elif isinstance(exc, AuthenticationFailed):
        body = {
            'error': 'Invalid or expired authentication.',
            'code': AUTHENTICATION_FAILED,
            'detail': str(exc.detail) if hasattr(exc, 'detail') else None,
        }
    elif isinstance(exc, PermissionDenied):
        body = {
            'error': str(exc.detail) if hasattr(exc, 'detail') else 'Permission denied.',
            'code': PERMISSION_DENIED,
            'detail': None,
        }
    elif isinstance(exc, Http404):
        body = {
            'error': 'Not found.',
            'code': NOT_FOUND,
            'detail': None,
        }
        response.status_code = 404
    elif response.status_code == 404:
        body = {
            'error': 'Not found.',
            'code': NOT_FOUND,
            'detail': None,
        }
    elif response.status_code == 400:
        body = {
            'error': 'Validation error.',
            'code': VALIDATION_ERROR,
            'detail': response.data,
        }
    else:
        body = {
            'error': str(response.data) if response.data else 'An error occurred.',
            'code': SERVER_ERROR,
            'detail': response.data,
        }

    response.data = body
    return response
