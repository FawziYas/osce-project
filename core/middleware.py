"""
Security middleware for the OSCE project.
"""
from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse


class AdminAccessMiddleware:
    """
    Double-lock protection for the Django admin.

    Layer 1 (Obscurity): Any request to the secret admin path without a valid
    session token is bounced to 404 — so even if the URL leaks, direct access
    is blocked.
    Layer 2 (Gate): /admin/ (the old default path) always returns 404, so
    automated scanners probing that path get nothing.

    To unlock: POST to the admin gateway view, which sets
    request.session['admin_unlocked'] = True then redirects using
    reverse('admin:index') — no hardcoded URLs anywhere.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        secret_prefix = f"/{settings.SECRET_ADMIN_URL}/"
        gateway_path = f"/{settings.SECRET_ADMIN_URL}/gateway/"

        # Block the default /admin/ path entirely — return 404 to scanners
        if request.path.startswith('/admin/'):
            raise Http404

        # Protect the secret admin path with a session gate,
        # but EXEMPT the gateway itself — it sets the session token
        # and has its own security (login + secret token check).
        if request.path.startswith(secret_prefix) and request.path != gateway_path:
            if not request.session.get('admin_unlocked'):
                # Fall back: if the user is already authenticated as staff
                # (e.g. session was cycled after a password change),
                # re-stamp the flag and let them through.
                user = getattr(request, 'user', None)
                if user is not None and user.is_authenticated and user.is_staff:
                    request.session['admin_unlocked'] = True
                else:
                    raise Http404

        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """
    Redirects any authenticated user whose profile has
    must_change_password=True to the force-change-password page.

    Exempted paths (to avoid redirect loops):
      - The force-change URL itself
      - /logout/
      - Static / media files
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Lazy-import to avoid circular imports at module load
            from core.models.user_profile import UserProfile

            profile = getattr(request.user, 'profile', None)
            if profile is None:
                # Safety net: create the profile if somehow missing
                profile, _ = UserProfile.objects.get_or_create(
                    user=request.user,
                    defaults={'must_change_password': False},
                )

            if profile.must_change_password:
                change_url = reverse('force_change_password')
                exempt = (
                    change_url,
                    reverse('logout'),
                    '/static/',
                )
                if not any(request.path.startswith(p) for p in exempt):
                    return redirect(change_url)

        return self.get_response(request)


class RoleBasedAccessMiddleware:
    """
    Enforces role-based access for /creator/ and /examiner/ routes:
        superuser  -> /creator/ only (not /examiner/ functional pages)
        admin      -> /creator/ only (not /examiner/ functional pages)
        coordinator -> /creator/ only (not /examiner/ functional pages)
        examiner   -> /examiner/ only (not /creator/)
    """

    # Examiner paths that are open to all authenticated users (auth/utility)
    EXAMINER_OPEN_PATHS = ('/examiner/login/', '/examiner/logout/',
                           '/examiner/offline/', '/examiner/profile/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            role = getattr(request.user, 'role', None)

            # Block non-examiners from /examiner/ functional pages
            if request.path.startswith('/examiner/'):
                is_open = any(
                    request.path.startswith(p) for p in self.EXAMINER_OPEN_PATHS
                )
                if not is_open:
                    if request.user.is_superuser or role in ('admin', 'coordinator'):
                        return redirect('/creator/')

            # Block examiners from /creator/
            if request.path.startswith('/creator/'):
                if not request.user.is_superuser and role not in ('admin', 'coordinator'):
                    return redirect('/examiner/home/')

        return self.get_response(request)



class ContentSecurityPolicyMiddleware:
    """
    Adds Content-Security-Policy header to all responses.
    Uses report-only mode by default for easy debugging; switch to enforcing
    by changing the header name.
    """

    # CSP directives - adjust per deployment needs
    CSP_DIRECTIVES = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src": "'self' https://cdn.jsdelivr.net https://fonts.gstatic.com",
        "img-src": "'self' data:",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "form-action": "'self'",
        "base-uri": "'self'",
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp_value = "; ".join(
            f"{key} {value}" for key, value in self.CSP_DIRECTIVES.items()
        )

    def __call__(self, request):
        response = self.get_response(request)
        # Use Content-Security-Policy for enforcing, or
        # Content-Security-Policy-Report-Only for monitoring.
        response["Content-Security-Policy"] = self.csp_value
        return response


class ReferrerPolicyMiddleware:
    """Sets the Referrer-Policy header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class PermissionsPolicyMiddleware:
    """Sets the Permissions-Policy header (formerly Feature-Policy)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        return response


class SessionTimeoutMiddleware:
    """
    Sets different session timeouts based on interface:
    - Creator interface: 5 minutes from last activity
    - Examiner interface: 30 minutes from last activity
    """
    
    # Session timeout in seconds
    CREATOR_TIMEOUT = 300  # 5 minutes
    EXAMINER_TIMEOUT = 1800  # 30 minutes
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only process for authenticated users
        if request.user.is_authenticated:
            # Determine timeout based on URL path
            if request.path.startswith('/creator/'):
                # Creator interface - 10 minute timeout
                request.session.set_expiry(self.CREATOR_TIMEOUT)
            elif request.path.startswith('/examiner/'):
                # Examiner interface - 30 minute timeout
                request.session.set_expiry(self.EXAMINER_TIMEOUT)
            # For other paths (admin, etc.), use Django's default
        
        response = self.get_response(request)
        return response
