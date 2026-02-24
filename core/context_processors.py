"""
Custom template context processors.
"""
from django.conf import settings


def admin_token(request):
    """
    Injects the SECRET_ADMIN_URL as ADMIN_TOKEN into every template context
    so the admin gateway form in base_creator.html can post it without
    hardcoding anything in the template itself.
    """
    return {'ADMIN_TOKEN': settings.SECRET_ADMIN_URL}
