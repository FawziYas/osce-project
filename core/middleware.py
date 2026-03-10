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

    For HTML page requests: returns an HTTP 302 redirect.
    For AJAX / API requests: returns an HTTP 403 JSON response so that
    API endpoints cannot be used while the password is still the default.

    Exempted paths (to avoid redirect loops):
      - The force-change URL itself
      - /logout/ and /examiner/logout/
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
                # Safety net: create the profile if somehow missing.
                # Default to must_change_password=True (secure default) —
                # only the force-change view or admin can clear this flag.
                profile, _ = UserProfile.objects.get_or_create(
                    user=request.user,
                    defaults={'must_change_password': True},
                )

            if profile.must_change_password:
                change_url = reverse('force_change_password')
                exempt = (
                    change_url,
                    reverse('logout'),
                    '/examiner/logout/',
                    '/static/',
                    '/media/',
                    '/favicon.ico',
                )
                if not any(request.path.startswith(p) for p in exempt):
                    # Block API / AJAX requests with a 403 JSON response
                    # so they can't bypass the password-change requirement
                    if (request.path.startswith('/api/') or
                            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                            'application/json' in request.headers.get('Accept', '')):
                        from django.http import JsonResponse
                        return JsonResponse(
                            {'error': 'Password change required',
                             'must_change_password': True,
                             'redirect': change_url},
                            status=403,
                        )
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

            # Block examiners from /creator/ AND /api/creator/
            if request.path.startswith('/creator/') or request.path.startswith('/api/creator/'):
                if not request.user.is_superuser and role not in ('admin', 'coordinator'):
                    if request.path.startswith('/api/'):
                        from django.http import JsonResponse
                        return JsonResponse(
                            {'error': 'Forbidden: creator role required'},
                            status=403,
                        )
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
    - Creator interface (admin/coordinator/superuser): 10 minutes from last activity
    - Examiner interface: 20 minutes from last activity
    """
    
    # Session timeout in seconds
    CREATOR_TIMEOUT = 600   # 10 minutes (admin, coordinator, superuser)
    EXAMINER_TIMEOUT = 1200  # 20 minutes (examiner)
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only process for authenticated users
        if request.user.is_authenticated:
            # Determine timeout based on URL path
            if request.path.startswith('/creator/'):
                # Creator interface (admin/coordinator/superuser) - 10 minute timeout
                request.session.set_expiry(self.CREATOR_TIMEOUT)
            elif request.path.startswith('/examiner/'):
                # Examiner interface - 20 minute timeout
                request.session.set_expiry(self.EXAMINER_TIMEOUT)
            # For other paths (admin, etc.), use Django's default
        
        response = self.get_response(request)
        return response


class UnauthorizedAccessMiddleware:
    """
    Intercepts 401, 403, and 404 responses and logs them as
    potential unauthorized access attempts to the audit log.

    Catches URL-sharing attacks and brute-force enumeration at
    the middleware layer.
    """

    # Status codes to intercept
    WATCHED_CODES = {401, 403, 404}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code in self.WATCHED_CODES:
            self._log_attempt(request, response)

        return response

    def _log_attempt(self, request, response):
        """Log the unauthorized/forbidden/not-found access attempt."""
        try:
            from core.utils.audit import AuditLogService
            from core.models.audit import (
                UNAUTHORIZED_ACCESS, STATUS_BLOCKED,
                EXAMINER_ACCESS_BLOCKED,
            )

            user = getattr(request, 'user', None)
            is_auth = user is not None and getattr(user, 'is_authenticated', False)

            # Skip logging for common static-file 404s
            static_exts = ('.ico', '.png', '.jpg', '.css', '.js', '.map', '.woff', '.woff2')
            if response.status_code == 404 and any(
                request.path.endswith(ext) for ext in static_exts
            ):
                return

            action = UNAUTHORIZED_ACCESS
            if response.status_code == 403 and is_auth:
                role = getattr(user, 'role', '')
                if role == 'examiner':
                    action = EXAMINER_ACCESS_BLOCKED

            AuditLogService.log(
                action=action,
                user=user if is_auth else None,
                request=request,
                resource_type='URL',
                resource_id='',
                resource_label_override=request.path[:200],
                status=STATUS_BLOCKED,
                description=(
                    f'HTTP {response.status_code} on {request.method} {request.path}'
                ),
                extra={
                    'status_code': response.status_code,
                    'method': request.method,
                    'path': request.path,
                },
            )
        except Exception:
            # Never break the response for a logging failure
            import logging
            logging.getLogger('osce.audit').error(
                'UnauthorizedAccessMiddleware failed', exc_info=True,
            )


class RLSSessionMiddleware:
    """
    Injects Django user context into the PostgreSQL session so
    Row-Level Security policies can read it via current_setting().

    Uses set_config(..., true) so variables are transaction-scoped
    and reset automatically after each request.

    Sets 4 session variables:
      app.current_user_id  - integer user PK
      app.current_role     - SUPERUSER / ADMIN / COORDINATOR_HEAD / etc.
      app.department_id    - department PK (coordinators only)
      app.station_ids      - comma-separated station UUIDs (examiners only)

    Automatically skipped on non-PostgreSQL databases.
    """

    # Map Django role + position to RLS role string
    _ROLE_MAP = {
        ('coordinator', 'head'):      'COORDINATOR_HEAD',
        ('coordinator', 'organizer'): 'COORDINATOR_ORGANIZER',
        ('coordinator', 'rta'):       'COORDINATOR_RTA',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._set_session_vars(request)
        return self.get_response(request)

    def _set_session_vars(self, request):
        """Set PostgreSQL session variables for RLS."""
        from django.db import connection

        if connection.vendor != 'postgresql':
            return

        user = getattr(request, 'user', None)
        user_id, role, dept_id, station_ids = self._resolve_vars(user)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT "
                "set_config('app.current_user_id', %s, true), "
                "set_config('app.current_role',    %s, true), "
                "set_config('app.department_id',   %s, true), "
                "set_config('app.station_ids',     %s, true)",
                [user_id, role, dept_id, station_ids],
            )

    def _resolve_vars(self, user):
        """Resolve (user_id, role, department_id, station_ids) from user."""
        if user is None or not getattr(user, 'is_authenticated', False):
            return ('', 'ANONYMOUS', '', '')

        user_id = str(user.pk)

        # Role resolution
        if user.is_superuser:
            role = 'SUPERUSER'
        elif getattr(user, 'role', '') == 'admin':
            role = 'ADMIN'
        elif getattr(user, 'role', '') == 'coordinator':
            position = getattr(user, 'coordinator_position', '') or ''
            role = self._ROLE_MAP.get(
                ('coordinator', position.lower()), 'COORDINATOR_HEAD'
            )
        else:
            role = 'EXAMINER'

        # Department
        dept = getattr(user, 'coordinator_department', None)
        dept_id = str(dept.pk) if dept else ''

        # Station IDs (for examiners)
        station_ids = ''
        if role == 'EXAMINER':
            from core.models import ExaminerAssignment
            ids = list(
                ExaminerAssignment.objects.filter(
                    examiner=user,
                ).values_list('station_id', flat=True)
            )
            station_ids = ','.join(str(s) for s in ids)

        return (user_id, role, dept_id, station_ids)
