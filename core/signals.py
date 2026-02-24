"""
Login audit signal handlers + auto-provisioning for new users.

Listens to Django's user_logged_in and user_login_failed signals
to create immutable LoginAuditLog records for every authentication attempt.

Also listens to post_save on the custom User model to:
  - assign the default password from settings.DEFAULT_USER_PASSWORD
  - create a UserProfile with must_change_password=True
"""
import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models.login_audit import LoginAuditLog

logger = logging.getLogger('osce.audit')
auth_logger = logging.getLogger('osce.auth')


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


@receiver(user_logged_out)
def cleanup_user_session(sender, request, user, **kwargs):
    """Remove the UserSession record when a user logs out."""
    if user is None:
        return
    try:
        from core.models.user_session import UserSession
        UserSession.objects.filter(user=user).delete()
        logger.info(
            'LOGOUT | user=%s | ip=%s',
            getattr(user, 'username', str(user)),
            _get_client_ip(request),
        )
    except Exception:
        pass  # Never crash the logout flow


# ── Auto-provision new users with default password + profile ──────────
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def provision_new_user(sender, instance, created, **kwargs):
    """
    On user creation:
      1. Set the password to settings.DEFAULT_USER_PASSWORD
         (unless the user is a superuser — they set their own via createsuperuser).
      2. Create a UserProfile with must_change_password=True
         (False for superusers — they already chose a password).
    """
    if not created:
        return

    from core.models.user_profile import UserProfile

    if instance.is_superuser:
        # Superusers set their own password via createsuperuser — don't override
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'must_change_password': False},
        )
        auth_logger.info(
            "Superuser '%s' created.  Profile created with must_change_password=False.",
            instance.username,
        )
    else:
        default_pw = getattr(settings, 'DEFAULT_USER_PASSWORD', '123456789')
        instance.set_password(default_pw)
        instance.save(update_fields=['password'])

        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'must_change_password': True},
        )

        auth_logger.info(
            "New user '%s' created.  Default password assigned.  must_change_password=True.",
            instance.username,
        )
