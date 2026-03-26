"""
AuditLogService — centralised audit logging for every significant action.

Usage:
    from core.utils.audit import AuditLogService

    AuditLogService.log(
        user=request.user,
        action='EXAM_CREATED',
        resource=exam_instance,
        request=request,
        new_value={'name': 'Midterm'},
    )

Async: when Celery is available, log writes are dispatched to a Celery
task so they never block the HTTP response.  Falls back to synchronous
writes when Celery is not configured.
"""
import json
import logging
import threading
import traceback

from django.conf import settings

logger = logging.getLogger('osce.audit')

# ── Per-request audit deduplication + current-user carrier (thread-local) ──
# Prevents AuditTrailMiddleware from adding a redundant HTTP-level
# entry when a view or signal already called AuditLogService.log().
# Also carries the authenticated user so signal-based log calls
# (which have no request) can still record who performed the action.

_audit_local = threading.local()


def _mark_request_audited():
    """Mark the current request thread as already having an audit entry."""
    _audit_local.logged = True


def _is_request_audited():
    """Return True if an audit entry was already written for this request."""
    return getattr(_audit_local, 'logged', False)


def _reset_request_audit():
    """Reset the dedup flag and current-user at the start of each new request."""
    _audit_local.logged = False
    _audit_local.current_user = None


def _set_current_user(user):
    """Store the authenticated request user so signals can read it."""
    _audit_local.current_user = user


def _get_current_user():
    """Return the user stored for this request thread, or None."""
    return getattr(_audit_local, 'current_user', None)


# ── Sensitive field masking ──────────────────────────────────────────

SENSITIVE_FIELDS = frozenset({
    'password', 'token', 'secret', 'key',
    'authorization', 'cookie', 'session',
    'credit_card', 'cvv', 'pin',
    'password1', 'password2', 'new_password',
    'old_password', 'csrfmiddlewaretoken',
})

_REDACTED = '***REDACTED***'


def _mask_sensitive(data):
    """Recursively mask values of sensitive keys in dicts/lists."""
    if data is None:
        return None
    if isinstance(data, dict):
        return {
            k: _REDACTED if k.lower() in SENSITIVE_FIELDS else _mask_sensitive(v)
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [_mask_sensitive(v) for v in data]
    return data


def _get_client_ip(request):
    """Extract client IP from request, respecting X-Forwarded-For."""
    if request is None:
        return None
    trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', [])
    remote_addr = request.META.get('REMOTE_ADDR', '')
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded and (not trusted_proxies or remote_addr in trusted_proxies):
        ip = x_forwarded.split(',')[0].strip()
    else:
        ip = remote_addr or None
    # Strip port if present (e.g., Azure proxy sends "IP:PORT")
    if ip and ':' in ip and '.' in ip:
        ip = ip.rsplit(':', 1)[0]
    return ip


def _resolve_department_id(resource):
    """
    Walk the hierarchy to find the department_id for a given resource.
    Returns an integer department_id or None.
    """
    if resource is None:
        return None

    # Direct department
    from core.models import Department
    if isinstance(resource, Department):
        return resource.pk

    # Has .department FK that points to Department
    dept_fk = getattr(resource, 'department', None)
    if dept_fk is not None:
        if isinstance(dept_fk, Department):
            return dept_fk.pk
        # Could be a string field on Exam
        if isinstance(dept_fk, str):
            pass  # Fall through to other resolution

    # Has department_id integer field
    dept_id = getattr(resource, 'department_id', None)
    if dept_id and isinstance(dept_id, int):
        return dept_id

    # Has coordinator_department FK (Examiner model) — now renamed to department
    # (handled above via getattr .department)

    # Course FK → department
    course = getattr(resource, 'course', None)
    if course is not None:
        dept = getattr(course, 'department', None)
        if dept is not None and hasattr(dept, 'pk'):
            return dept.pk

    # Exam FK → course → department
    exam = getattr(resource, 'exam', None)
    if exam is not None:
        return _resolve_department_id(exam)

    # Session FK → exam → course → department
    session = getattr(resource, 'session', None)
    if session is not None:
        return _resolve_department_id(session)

    # Path FK → session
    path = getattr(resource, 'path', None)
    if path is not None:
        return _resolve_department_id(path)

    # Station FK → path
    station = getattr(resource, 'station', None)
    if station is not None:
        return _resolve_department_id(station)

    return None


def _resolve_user_role(user):
    """Return the role string for the user at this moment."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'anonymous'
    if user.is_superuser:
        return 'superuser'
    return getattr(user, 'role', 'examiner')


def _make_serialisable(val):
    """Ensure a value is JSON-serialisable."""
    if val is None:
        return None
    if isinstance(val, dict):
        return {k: _make_serialisable(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_make_serialisable(v) for v in val]
    if isinstance(val, (str, int, float, bool)):
        return val
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)


class AuditLogService:
    """
    Centralised audit logging service.

    Never raises exceptions — failures are written to the error log.
    """

    @staticmethod
    def log(
        action,
        resource=None,
        *,
        user=None,
        request=None,
        resource_type=None,
        resource_id=None,
        resource_label_override=None,
        old_value=None,
        new_value=None,
        description='',
        status=None,
        extra=None,
        department_id=None,
    ):
        """
        Record an audit log entry.

        Parameters
        ----------
        action : str
            One of the ACTION_TYPE constants from core.models.audit.
        resource : Model instance, optional
            The Django model instance being acted upon.
        user : User instance, optional
            The user performing the action (overrides request.user).
        request : HttpRequest, optional
            Current HTTP request (for IP, user-agent, method, path).
        resource_type : str, optional
            Override the resource type label.
        resource_id : str, optional
            Override the resource ID.
        resource_label_override : str, optional
            Override the human-readable label.
        old_value : dict, optional
            Previous state for UPDATE/DELETE actions.
        new_value : dict, optional
            New state for CREATE/UPDATE actions.
        description : str
            Human-readable description of the action.
        status : str, optional
            One of STATUS_SUCCESS / STATUS_BLOCKED / STATUS_FAILED.
        extra : dict, optional
            Additional context data.
        department_id : int, optional
            Override the department ID resolution.
        """
        try:
            from core.models.audit import STATUS_SUCCESS

            # Resolve user from request if not provided
            if user is None and request is not None:
                u = getattr(request, 'user', None)
                if u is not None and getattr(u, 'is_authenticated', False):
                    user = u

            # Last-resort fallback: use the thread-local user stored by
            # AuditTrailMiddleware (covers signal-based calls with no request)
            if user is None:
                u = _get_current_user()
                if u is not None and getattr(u, 'is_authenticated', False):
                    user = u

            # Build the log payload (all primitive types for Celery serialisation)
            payload = {
                'user_id': user.pk if user and hasattr(user, 'pk') else None,
                'username': getattr(user, 'username', '') if user else '',
                'user_role': _resolve_user_role(user),
                'action': action,
                'status': status or STATUS_SUCCESS,
                'resource_type': resource_type or (
                    type(resource).__name__ if resource else ''
                ),
                'resource_id': str(resource_id or (
                    getattr(resource, 'pk', '') if resource else ''
                )),
                'resource_label': resource_label_override or (
                    str(resource)[:200] if resource else ''
                ),
                'department_id': department_id or (
                    _resolve_department_id(resource) if resource else None
                ),
                'old_value': _mask_sensitive(_make_serialisable(old_value)),
                'new_value': _mask_sensitive(_make_serialisable(new_value)),
                'description': description[:1000] if description else '',
                'ip_address': _get_client_ip(request) if request else None,
                'user_agent': (
                    request.META.get('HTTP_USER_AGENT', '')[:500]
                    if request else ''
                ),
                'request_method': (
                    getattr(request, 'method', '') or ''
                    if request else ''
                ),
                'request_path': (
                    getattr(request, 'path', '')[:500]
                    if request else ''
                ),
                'extra_data': _mask_sensitive(_make_serialisable(extra)),
            }

            # Dispatch to Celery if available, else write synchronously
            if _celery_available():
                from core.tasks import write_audit_log
                write_audit_log.delay(payload)
            else:
                _write_audit_log_sync(payload)

            # Mark this request thread so middleware won't double-log.
            # Works even when called from signals (no request object).
            _mark_request_audited()

        except Exception:
            logger.error(
                'AuditLogService.log failed: %s',
                traceback.format_exc(),
            )

    @staticmethod
    def log_bulk(entries):
        """
        Record multiple audit log entries efficiently (single Celery task / bulk_create).

        Parameters
        ----------
        entries : list[dict]
            Each dict should have keys matching AuditLogService.log() parameters:
            action, resource_type, resource_id, user_id, username, description, etc.
        """
        try:
            from core.models.audit import STATUS_SUCCESS

            payloads = []
            for entry in entries:
                payloads.append({
                    'user_id': entry.get('user_id'),
                    'username': entry.get('username', ''),
                    'user_role': entry.get('user_role', ''),
                    'action': entry.get('action', ''),
                    'status': entry.get('status', STATUS_SUCCESS),
                    'resource_type': entry.get('resource_type', ''),
                    'resource_id': str(entry.get('resource_id', '')),
                    'resource_label': entry.get('resource_label', '')[:200] if entry.get('resource_label') else '',
                    'department_id': entry.get('department_id'),
                    'old_value': _mask_sensitive(_make_serialisable(entry.get('old_value'))),
                    'new_value': _mask_sensitive(_make_serialisable(entry.get('new_value'))),
                    'description': (entry.get('description', '') or '')[:1000],
                    'ip_address': entry.get('ip_address'),
                    'user_agent': (entry.get('user_agent', '') or '')[:500],
                    'request_method': entry.get('request_method', '') or '',
                    'request_path': (entry.get('request_path', '') or '')[:500],
                    'extra_data': _mask_sensitive(_make_serialisable(entry.get('extra_data'))),
                })

            if _celery_available():
                from core.tasks import write_audit_log_batch
                write_audit_log_batch.delay(payloads)
            else:
                _write_audit_log_bulk_sync(payloads)

        except Exception:
            logger.error(
                'AuditLogService.log_bulk failed: %s',
                traceback.format_exc(),
            )


def _celery_available():
    """Check if Celery is configured and reachable."""
    try:
        if not getattr(settings, 'CELERY_BROKER_URL', None):
            return False
        from core.tasks import write_audit_log  # noqa: F401
        return True
    except Exception:
        return False


def _write_audit_log_sync(payload):
    """
    Synchronous fallback — writes the audit log directly to the DB.
    Used when Celery is not available.
    """
    try:
        from core.models.audit import AuditLog

        AuditLog.objects.create(
            user_id=payload.get('user_id'),
            username=payload.get('username', ''),
            user_role=payload.get('user_role', ''),
            department_id=payload.get('department_id'),
            action=payload.get('action', ''),
            status=payload.get('status', 'SUCCESS'),
            resource_type=payload.get('resource_type', ''),
            resource_id=payload.get('resource_id', ''),
            resource_label=payload.get('resource_label', ''),
            old_value=payload.get('old_value'),
            new_value=payload.get('new_value'),
            description=payload.get('description', ''),
            ip_address=payload.get('ip_address'),
            user_agent=payload.get('user_agent') or '',
            request_method=payload.get('request_method') or '',
            request_path=payload.get('request_path') or '',
            extra_data=payload.get('extra_data'),
        )
    except Exception:
        logger.error(
            'Sync audit log write failed: %s',
            traceback.format_exc(),
        )


def _write_audit_log_bulk_sync(payloads):
    """Synchronous bulk fallback — writes multiple audit logs in one DB call."""
    try:
        from core.models.audit import AuditLog, compute_checksum

        objs = [
            AuditLog(
                user_id=p.get('user_id'),
                username=p.get('username', ''),
                user_role=p.get('user_role', ''),
                department_id=p.get('department_id'),
                action=p.get('action', ''),
                status=p.get('status', 'SUCCESS'),
                resource_type=p.get('resource_type', ''),
                resource_id=p.get('resource_id', ''),
                resource_label=p.get('resource_label', ''),
                old_value=p.get('old_value'),
                new_value=p.get('new_value'),
                description=p.get('description', ''),
                ip_address=p.get('ip_address'),
                user_agent=p.get('user_agent') or '',
                request_method=p.get('request_method') or '',
                request_path=p.get('request_path') or '',
                extra_data=p.get('extra_data'),
            )
            for p in payloads
        ]
        # Insert first so auto_now_add sets timestamps, then compute checksums.
        AuditLog.objects.bulk_create(objs)
        pk_list = [obj.pk for obj in objs if obj.pk]
        if pk_list:
            db_rows = list(
                AuditLog.objects.filter(pk__in=pk_list, checksum='')
                .only('pk', 'user_id', 'action', 'resource_id',
                      'timestamp', 'old_value', 'new_value')
            )
            for row in db_rows:
                row.checksum = compute_checksum(
                    row.user_id, row.action, row.resource_id,
                    row.timestamp, row.old_value, row.new_value,
                )
            if db_rows:
                AuditLog.objects.bulk_update(db_rows, ['checksum'])
    except Exception:
        logger.error(
            'Sync bulk audit log write failed: %s',
            traceback.format_exc(),
        )


# ── Backwards-compatible helper ──────────────────────────────────────

def log_action(request, action, resource_type, resource_id='',
               description='', extra_data=None):
    """
    Legacy helper — wraps AuditLogService.log() for old call sites.
    """
    AuditLogService.log(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        request=request,
        description=description,
        extra=extra_data,
    )
