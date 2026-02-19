"""
Custom error handlers for production - sanitize error messages.
"""
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token


@requires_csrf_token
def handler404(request, exception=None):
    """Custom 404 error handler."""
    return render(request, 'errors/404.html', status=404)


@requires_csrf_token
def handler500(request):
    """Custom 500 error handler - sanitize error details in production."""
    return render(request, 'errors/500.html', status=500)


@requires_csrf_token
def handler403(request, exception=None):
    """Custom 403 error handler."""
    return render(request, 'errors/403.html', status=403)


@requires_csrf_token
def handler400(request, exception=None):
    """Custom 400 error handler."""
    return render(request, 'errors/400.html', status=400)
