"""
Audit signal handlers — login/logout, user provisioning, and hierarchy model signals.

Listens to:
  - Django's user_logged_in / user_login_failed / user_logged_out signals
  - post_save / post_delete on all hierarchy models (Department, Course,
    Exam, ExamSession, Path, Station, ChecklistItem, ExaminerAssignment)

Every significant change is recorded in the AuditLog via AuditLogService.
"""
import logging
import threading

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver

from core.models.login_audit import LoginAuditLog

logger = logging.getLogger('osce.audit')
auth_logger = logging.getLogger('osce.auth')

# Thread-local storage to carry pre-save snapshots to post_save
_pre_save_state = threading.local()


def _get_client_ip(request):
    """
    Extract the real client IP from the request.
    """
    if request is None:
        return None

    trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', [])
    remote_addr = request.META.get('REMOTE_ADDR', '')
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded and (not trusted_proxies or remote_addr in trusted_proxies):
        return x_forwarded.split(',')[0].strip()

    return remote_addr or None


# ── Authentication signals ────────────────────────────────────────────

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

    # Also log to the main AuditLog
    from core.utils.audit import AuditLogService
    from core.models.audit import LOGIN_SUCCESS
    AuditLogService.log(
        user=user,
        action=LOGIN_SUCCESS,
        resource=user,
        request=request,
        description=f'{getattr(user, "username", "")} logged in',
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

    from core.utils.audit import AuditLogService
    from core.models.audit import LOGIN_FAILED, STATUS_FAILED
    AuditLogService.log(
        user=None,
        action=LOGIN_FAILED,
        request=request,
        resource_type='User',
        resource_label_override=username,
        description=f'Failed login attempt for "{username}"',
        status=STATUS_FAILED,
    )


@receiver(user_logged_out)
def cleanup_user_session(sender, request, user, **kwargs):
    """Remove the UserSession record when a user logs out."""
    if user is None:
        return

    # Log to main AuditLog
    from core.utils.audit import AuditLogService
    from core.models.audit import LOGOUT
    AuditLogService.log(
        user=user,
        action=LOGOUT,
        resource=user,
        request=request,
        description=f'{getattr(user, "username", "")} logged out',
    )

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


# ── Auto-assign permissions based on role ────────────────────────────
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def sync_role_permissions(sender, instance, **kwargs):
    """
    Automatically grant/revoke the can_view_student_list permission based on role:
      - Superusers:  always have all permissions (no explicit assignment needed)
      - Admin role:  granted automatically
      - Coordinator + head position: granted automatically
      - All others:  permission removed
    """
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.models import Permission

    if instance.is_superuser:
        return  # Superusers implicitly have all permissions

    try:
        ct = ContentType.objects.get(app_label='core', model='sessionstudent')
        perm = Permission.objects.get(codename='can_view_student_list', content_type=ct)
    except (ContentType.DoesNotExist, Permission.DoesNotExist):
        return  # Permission not created yet (e.g. during initial migration)

    is_admin = getattr(instance, 'role', None) == 'admin'
    is_head = (
        getattr(instance, 'role', None) == 'coordinator' and
        getattr(instance, 'coordinator_position', None) == 'head'
    )

    if is_admin or is_head:
        instance.user_permissions.add(perm)
    else:
        instance.user_permissions.remove(perm)



# Hierarchy model audit signals
# ══════════════════════════════════════════════════════════════════════

# Map of model class name → (created_action, updated_action, deleted_action)
_HIERARCHY_ACTION_MAP = {
    'Department':          ('DEPT_CREATED',      'DEPT_UPDATED',      'DEPT_DELETED'),
    'Course':              ('COURSE_CREATED',     'COURSE_UPDATED',    'COURSE_DELETED'),
    'Exam':                ('EXAM_CREATED',       'EXAM_UPDATED',      'EXAM_DELETED'),
    'ExamSession':         ('SESSION_CREATED',    'SESSION_UPDATED',   'SESSION_DELETED'),
    'Path':                ('PATH_CREATED',       'PATH_UPDATED',      'PATH_DELETED'),
    'Station':             ('STATION_CREATED',    'STATION_UPDATED',   'STATION_DELETED'),
    'ChecklistItem':       ('CHECKLIST_CREATED',  'CHECKLIST_UPDATED', 'CHECKLIST_DELETED'),
    'ExaminerAssignment':  ('EXAMINER_ASSIGNED',  'EXAMINER_ASSIGNED', 'EXAMINER_UNASSIGNED'),
}

# Fields to track for old/new value diffs per model
_TRACKED_FIELDS = {
    'Department':     ('name',),
    'Course':         ('code', 'name', 'year_level', 'department_id', 'osce_mark'),
    'Exam':           ('name', 'exam_date', 'status', 'is_deleted', 'exam_weight',
                       'number_of_stations', 'station_duration_minutes'),
    'ExamSession':    ('name', 'session_date', 'status', 'session_type', 'start_time',
                       'number_of_stations', 'number_of_paths'),
    'Path':           ('name', 'rotation_minutes', 'is_active', 'is_deleted'),
    'Station':        ('station_number', 'name', 'duration_minutes', 'active', 'is_deleted'),
    'ChecklistItem':  ('item_number', 'description', 'points', 'rubric_type'),
    'ExaminerAssignment': ('examiner_id', 'station_id', 'session_id'),
}


def _snapshot(instance, model_name):
    """Take a dict snapshot of tracked fields for a model instance."""
    fields = _TRACKED_FIELDS.get(model_name, ())
    data = {}
    for f in fields:
        val = getattr(instance, f, None)
        # Convert non-serialisable types
        if hasattr(val, 'isoformat'):
            val = val.isoformat()
        elif hasattr(val, '__str__') and not isinstance(val, (str, int, float, bool, type(None))):
            val = str(val)
        data[f] = val
    return data


def _hierarchy_pre_save(sender, instance, **kwargs):
    """
    Capture the database state before save so we can diff in post_save.
    Only fetches for UPDATE (existing PK).
    """
    model_name = type(instance).__name__
    if model_name not in _HIERARCHY_ACTION_MAP:
        return

    pk = instance.pk
    if pk is None:
        return  # New instance — no old state

    try:
        old = type(instance).objects.filter(pk=pk).first()
        if old:
            key = f'{model_name}_{pk}'
            if not hasattr(_pre_save_state, 'snapshots'):
                _pre_save_state.snapshots = {}
            _pre_save_state.snapshots[key] = _snapshot(old, model_name)
    except Exception:
        pass  # Never block the save


def _hierarchy_post_save(sender, instance, created, **kwargs):
    """Log CREATE or UPDATE for a hierarchy model."""
    model_name = type(instance).__name__
    actions = _HIERARCHY_ACTION_MAP.get(model_name)
    if not actions:
        return

    from core.utils.audit import AuditLogService

    action = actions[0] if created else actions[1]
    new_val = _snapshot(instance, model_name)
    old_val = None

    if not created:
        key = f'{model_name}_{instance.pk}'
        old_val = getattr(_pre_save_state, 'snapshots', {}).pop(key, None)

        # If nothing actually changed, skip logging
        if old_val and old_val == new_val:
            return

    AuditLogService.log(
        action=action,
        resource=instance,
        old_value=old_val,
        new_value=new_val,
        description=f'{model_name} {"created" if created else "updated"}',
    )


def _hierarchy_post_delete(sender, instance, **kwargs):
    """Log DELETE for a hierarchy model."""
    model_name = type(instance).__name__
    actions = _HIERARCHY_ACTION_MAP.get(model_name)
    if not actions:
        return

    from core.utils.audit import AuditLogService

    old_val = _snapshot(instance, model_name)

    AuditLogService.log(
        action=actions[2],
        resource=instance,
        old_value=old_val,
        description=f'{model_name} deleted',
    )


def connect_hierarchy_signals():
    """
    Connect pre_save / post_save / post_delete signals for all hierarchy
    models.  Called from CoreConfig.ready().
    """
    from core.models import (
        Department, Course, Exam, ExamSession, Path, Station,
        ChecklistItem, ExaminerAssignment,
    )
    hierarchy_models = [
        Department, Course, Exam, ExamSession, Path, Station,
        ChecklistItem, ExaminerAssignment,
    ]
    for model in hierarchy_models:
        pre_save.connect(_hierarchy_pre_save, sender=model, dispatch_uid=f'audit_pre_{model.__name__}')
        post_save.connect(_hierarchy_post_save, sender=model, dispatch_uid=f'audit_post_{model.__name__}')
        post_delete.connect(_hierarchy_post_delete, sender=model, dispatch_uid=f'audit_del_{model.__name__}')
