"""
Custom template context processors.
"""
from django.conf import settings


def admin_token(request):
    """
    Injects the SECRET_ADMIN_URL as ADMIN_TOKEN into every template context
    so the admin gateway form in base_creator.html can post it without
    hardcoding anything in the template itself.
    Only exposed to staff/superuser to prevent leaking to examiner templates.
    """
    if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
        return {'ADMIN_TOKEN': settings.SECRET_ADMIN_URL}
    return {'ADMIN_TOKEN': ''}
