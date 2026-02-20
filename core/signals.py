"""
Login audit signal handlers.

Listens to Django's user_logged_in and user_login_failed signals
to create immutable LoginAuditLog records for every authentication attempt.
"""
import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from core.models.login_audit import LoginAuditLog

logger = logging.getLogger('osce.audit')


def _get_client_ip(request):
    """
    Extract the real client IP from the request.

    Supports reverse-proxy setups:
    - If HTTP_X_FORWARDED_FOR is present AND the request came from a
      trusted proxy (TRUSTED_PROXIES in settings), use the first IP.
    - Otherwise fall back to REMOTE_ADDR.
    """
    if request is None:
        return None

    trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', [])
    remote_addr = request.META.get('REMOTE_ADDR', '')
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded and (not trusted_proxies or remote_addr in trusted_proxies):
        # First IP in the chain is the original client
        return x_forwarded.split(',')[0].strip()

    return remote_addr or None


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    """Record a successful login attempt."""
    ip = _get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''

    LoginAuditLog.objects.create(
        user=user,
        username_attempted=getattr(user, 'username', str(user)),
        ip_address=ip,
        user_agent=user_agent,
        success=True,
    )

    logger.info(
        'LOGIN_SUCCESS | user=%s | ip=%s | ua=%s',
        getattr(user, 'username', str(user)),
        ip,
        user_agent[:120],
    )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Record a failed login attempt."""
    ip = _get_client_ip(request) if request else None
    user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
    username = credentials.get('username', '<unknown>')

    LoginAuditLog.objects.create(
        user=None,
        username_attempted=username,
        ip_address=ip,
        user_agent=user_agent,
        success=False,
    )

    logger.warning(
        'LOGIN_FAILED | username=%s | ip=%s | ua=%s',
        username,
        ip,
        user_agent[:120],
    )
