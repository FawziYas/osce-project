"""
Audit logging utility for recording user actions.
"""
from core.models.audit import AuditLog
from core.models.mixins import TimestampMixin


def log_action(request, action, resource_type, resource_id='', description='', extra_data=None):
    """
    Create an audit log entry.

    Args:
        request: Django HttpRequest (can be None for system actions)
        action: Action type string (CREATE, UPDATE, DELETE, LOGIN, etc.)
        resource_type: Model name or resource category
        resource_id: Primary key of affected resource
        description: Human-readable description
        extra_data: Optional dict with extra context
    """
    user = None
    username = 'system'
    ip_address = None
    user_agent = ''

    if request:
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            username = user.username
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

    AuditLog.objects.create(
        user=user,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=extra_data,
        timestamp=TimestampMixin.utc_timestamp(),
    )


def _get_client_ip(request):
    """Extract client IP from request, respecting X-Forwarded-For."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
