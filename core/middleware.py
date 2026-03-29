"""
Security middleware for the OSCE project.
"""
import time

from django.conf import settings
from django.http import Http404, JsonResponse
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

            # Fast path: check session cache first to avoid a DB query on
            # every single authenticated request.
            must_change = request.session.get('_must_change_password')
            if must_change is None:
                # First request after login (or session has no cached flag)
                profile = getattr(request.user, 'profile', None)
                if profile is None:
                    profile, _ = UserProfile.objects.get_or_create(
                        user=request.user,
                        defaults={'must_change_password': True},
                    )
                must_change = profile.must_change_password
                request.session['_must_change_password'] = must_change

            if must_change:
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
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
        "font-src": "'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com",
        "img-src": "'self' data: blob: https://myoscemedia.blob.core.windows.net",
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
    Enforces idle-based session timeouts per user role:
    - Creator roles (superuser / admin / coordinator): 10 minutes of inactivity
    - Examiner role: 20 minutes of inactivity

    On every authenticated request the middleware:
    1. Checks how long ago the user last made ANY request (page load OR API call).
    2. If idle longer than the allowed timeout → forces logout and redirects to login
       (or returns 401 JSON for AJAX/API callers).
    3. Otherwise → stamps the session with the current timestamp so the clock
       resets from THIS request, not from login time.

    Covering ALL paths (not just /creator/ and /examiner/) is what makes
    API / AJAX calls count as real user activity.
    """

    CREATOR_TIMEOUT = 600    # 10 minutes — superuser, admin, coordinator
    EXAMINER_TIMEOUT = 1200  # 20 minutes — examiner

    # Paths that must never trigger a timeout redirect (avoid loops)
    EXEMPT_PATHS = (
        '/login/',
        '/logout/',
        '/examiner/login/',
        '/examiner/logout/',
        '/static/',
        '/media/',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def _timeout_for(self, user):
        """Return idle timeout seconds based on the user's role."""
        role = getattr(user, 'role', None)
        if user.is_superuser or role in ('admin', 'coordinator'):
            return self.CREATOR_TIMEOUT
        return self.EXAMINER_TIMEOUT

    def __call__(self, request):
        if request.user.is_authenticated:
            if not any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
                timeout = self._timeout_for(request.user)
                now = time.time()
                last_activity = request.session.get('_last_activity')

                if last_activity is not None and (now - last_activity) > timeout:
                    # User has been idle too long — force a clean logout
                    from django.contrib.auth import logout as _logout
                    from django.contrib import messages as _messages
                    _logout(request)

                    # AJAX / API callers get a JSON 401 so the front-end can
                    # redirect gracefully instead of receiving an HTML page
                    is_ajax = (
                        request.path.startswith('/api/')
                        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                        or 'application/json' in request.headers.get('Accept', '')
                    )
                    if is_ajax:
                        return JsonResponse(
                            {'error': 'Session expired due to inactivity.',
                             'redirect': '/login/'},
                            status=401,
                        )

                    _messages.warning(
                        request,
                        'Your session has expired due to inactivity. Please log in again.',
                    )
                    return redirect('/login/')

                # Still active — stamp the session so the idle clock resets
                # from THIS request.
                # Note: SESSION_SAVE_EVERY_REQUEST=True already slides the
                # cookie expiry, so we only call set_expiry() once (first hit)
                # to avoid marking the session modified a second time.
                request.session['_last_activity'] = now
                if request.session.get('_timeout') != timeout:
                    request.session.set_expiry(timeout)
                    request.session['_timeout'] = timeout

        return self.get_response(request)


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

    Uses set_config(..., false) so variables are session-scoped
    (persist on the connection for all queries within the request).

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
        import logging
        from django.db import connection

        if connection.vendor != 'postgresql':
            return

        user = getattr(request, 'user', None)
        user_id, role, dept_id = self._resolve_vars(user)

        try:
            # Set core vars first so RLS policies work for any follow-up queries
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT "
                    "set_config('app.current_user_id', %s, false), "
                    "set_config('app.current_role',    %s, false), "
                    "set_config('app.department_id',   %s, false), "
                    "set_config('app.station_ids',     %s, false)",
                    [user_id, role, dept_id, ''],
                )

            # Now that RLS vars are set, resolve station_ids for examiners
            if role == 'EXAMINER' and user_id:
                station_ids = self._resolve_station_ids(user)
                if station_ids:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('app.station_ids', %s, false)",
                            [station_ids],
                        )
        except Exception:
            logger = logging.getLogger('django.request')
            logger.exception(
                'RLSSessionMiddleware: failed to set session vars '
                '(user_id=%s, role=%s)', user_id, role,
            )

    def _resolve_vars(self, user):
        """Resolve (user_id, role, department_id) from user model fields only.

        Avoids any FK traversal that would hit RLS-protected tables.
        """
        if user is None or not getattr(user, 'is_authenticated', False):
            return ('', 'ANONYMOUS', '')

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

        # Use raw FK column — no query to RLS-protected departments table
        raw_dept_id = getattr(user, 'department_id', None)
        dept_id = str(raw_dept_id) if raw_dept_id else ''

        return (user_id, role, dept_id)

    def _resolve_station_ids(self, user):
        """Resolve station IDs for examiner. Called AFTER set_config."""
        from core.models import ExaminerAssignment
        ids = list(
            ExaminerAssignment.objects.filter(
                examiner=user,
            ).values_list('station_id', flat=True)
        )
        return ','.join(str(s) for s in ids)

        return (user_id, role, dept_id, station_ids)


class AuditTrailMiddleware:
    """
    Global audit trail — logs every successful mutating HTTP request
    (POST, PUT, PATCH, DELETE) via Celery for async persistence.

    This acts as a safety net so that even if a specific view doesn't
    call AuditLogService.log(), there is still a record of the action
    at the HTTP level.

    Skips:
      - GET / HEAD / OPTIONS requests (read-only)
      - Failed responses (4xx/5xx — handled by UnauthorizedAccessMiddleware)
      - Static / media file requests
      - Login / logout (already logged by signals)
      - CSRF validation requests
    """

    MUTATING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

    SKIP_PATHS = (
        '/static/',
        '/media/',
        '/favicon.ico',
        '/login/',
        '/logout/',
        '/examiner/login/',
        '/examiner/logout/',
        '/health/',
        '/metrics/',
        '/ping/',
        '/api/schema/',
        '/api/docs/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Reset the per-request audit flag and store the current user so
        # signal-based log calls (which have no request) can read it.
        from core.utils.audit import (
            _reset_request_audit, _is_request_audited, _set_current_user,
        )
        _reset_request_audit()
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            _set_current_user(user)

        response = self.get_response(request)

        if (
            request.method in self.MUTATING_METHODS
            and 200 <= response.status_code < 400
            and not any(request.path.startswith(p) for p in self.SKIP_PATHS)
            and not _is_request_audited()
        ):
            self._log_request(request, response)

        return response

    def _log_request(self, request, response):
        """Dispatch the audit entry to Celery (or sync fallback)."""
        try:
            from core.utils.audit import AuditLogService, _get_client_ip, _resolve_user_role, _mask_sensitive

            user = getattr(request, 'user', None)
            is_auth = user is not None and getattr(user, 'is_authenticated', False)

            # Capture request body for POST/PUT/PATCH (with sensitive masking)
            request_body = None
            if request.method in ('POST', 'PUT', 'PATCH'):
                try:
                    import json as _json
                    content_type = request.content_type or ''
                    if 'json' in content_type:
                        body = _json.loads(request.body)
                        request_body = _mask_sensitive(body)
                    elif 'form' in content_type:
                        request_body = _mask_sensitive(dict(request.POST))
                except Exception:
                    pass  # Don't fail on unparseable body

            AuditLogService.log(
                action='ADMIN_ACTION',
                user=user if is_auth else None,
                request=request,
                resource_type='HTTP',
                resource_id='',
                resource_label_override=request.path[:200],
                description=f'{request.method} {request.path} → {response.status_code}',
                extra={
                    'http_method': request.method,
                    'http_status': response.status_code,
                    'content_type': response.get('Content-Type', ''),
                    'request_body': request_body,
                },
            )
        except Exception:
            import logging
            logging.getLogger('osce.audit').error(
                'AuditTrailMiddleware failed', exc_info=True,
            )


class SearchEngineBlockingMiddleware:
    """
    Adds X-Robots-Tag header to all responses to prevent search engine indexing.
    This is a private exam management system and must not be indexed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
