"""
Security middleware for the OSCE project.
"""
from django.shortcuts import redirect


class RoleBasedAccessMiddleware:
    """
    Enforces /creator/ access based on role hierarchy:
        superuser  -> full access
        admin      -> /creator/ access
        coordinator -> /creator/ access
        examiner   -> /examiner/ only
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/creator/') and request.user.is_authenticated:
            role = getattr(request.user, 'role', None)
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
