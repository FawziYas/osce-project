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
    if kwargs.get('raw'):
        # Skip during fixture loading (loaddata uses raw=True) — data comes from the fixture itself
        return
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
        if getattr(instance, 'is_dry_user', False):
            # Dry users need to log in but should not be forced to change their password.
            default_pw = getattr(settings, 'DEFAULT_USER_PASSWORD', '12345678F')
            instance.set_password(default_pw)
            instance.save(update_fields=['password'])
            UserProfile.objects.get_or_create(
                user=instance,
                defaults={'must_change_password': False},
            )
            auth_logger.info(
                "Dry user '%s' created.  Default password assigned.  must_change_password=False.",
                instance.username,
            )
        else:
            default_pw = getattr(settings, 'DEFAULT_USER_PASSWORD', '12345678F')
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

    # Invalidate the examiner list cache so the new user appears immediately
    try:
        from core.utils.cache_utils import invalidate_examiner_list
        invalidate_examiner_list()
    except Exception:
        pass


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

    role = getattr(instance, 'role', None)
    position = getattr(instance, 'coordinator_position', None)

    is_admin = role == 'admin'
    is_head = role == 'coordinator' and position == 'head'

    if is_admin or is_head:
        instance.user_permissions.add(perm)
    else:
        instance.user_permissions.remove(perm)

    # ── can_open_dry_grading: admin, coordinator-head, coordinator-organizer ──
    try:
        ct_session = ContentType.objects.get(app_label='core', model='examsession')
        dry_perm = Permission.objects.get(codename='can_open_dry_grading', content_type=ct_session)
    except (ContentType.DoesNotExist, Permission.DoesNotExist):
        return  # Permission not created yet

    can_dry = (
        is_admin
        or (role == 'coordinator' and position in ('head', 'organizer'))
    )

    if can_dry:
        instance.user_permissions.add(dry_perm)
    else:
        instance.user_permissions.remove(dry_perm)



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
    
    # Connect scoring sync signals for ChecklistItem changes
    post_save.connect(
        sync_station_max_score,
        sender=ChecklistItem,
        dispatch_uid='sync_max_score_on_item_save',
    )
    post_delete.connect(
        sync_station_max_score,
        sender=ChecklistItem,
        dispatch_uid='sync_max_score_on_item_delete',
    )


# ── Sync max_score + ItemScore rescaling when checklist item points change ─
def sync_station_max_score(sender, instance, **kwargs):
    """
    Whenever a ChecklistItem is saved or deleted:

    1. ITEM-LEVEL: For every existing ItemScore for this item, rescale the
       student's earned score based on the old/new points ratio:
         - full marks (score == old_max_points)  → award new full points
         - zero (wrong / not done)               → keep 0, update max_points
         - partial                               → scale proportionally
       Then update max_points to the new value.

    2. STATION-LEVEL: Recompute total_score and max_score on every
       StationScore for this station (including already-submitted rows).
    """
    from core.models.scoring import StationScore, ItemScore

    new_item_points = instance.points  # new points value (0 after delete)

    # ── Step 1: Rescale ItemScore rows for this checklist item ──────────
    item_scores = list(
        ItemScore.objects.filter(checklist_item=instance)
        if instance.pk else ItemScore.objects.none()
    )

    is_mcq = instance.rubric_type == 'mcq'
    if is_mcq:
        # For MCQ items the student's selected option index is stored in notes.
        # Re-evaluate: correct index → full marks, anything else → 0.
        rubric_levels = instance.rubric_levels or {}
        correct_index = rubric_levels.get('correct_index', -1)
        try:
            correct_index = int(correct_index)
        except (TypeError, ValueError):
            correct_index = -1

    updated_item_scores = []
    for item_score in item_scores:
        old_max = item_score.max_points or 0
        old_score = item_score.score or 0

        if is_mcq:
            # Parse the student's saved selected option index from notes
            try:
                selected_index = int(item_score.notes)
            except (TypeError, ValueError):
                selected_index = -1  # no valid answer recorded
            new_score = new_item_points if (correct_index >= 0 and selected_index == correct_index) else 0
        elif old_max > 0:
            if old_score >= old_max:
                # Full marks → award new full points
                new_score = new_item_points
            elif old_score == 0:
                # Wrong / not done → stays at 0
                new_score = 0
            else:
                # Partial credit → scale proportionally
                new_score = round(old_score / old_max * new_item_points, 2)
        else:
            new_score = 0

        item_score.score = new_score
        item_score.max_points = new_item_points
        updated_item_scores.append(item_score)

    if updated_item_scores:
        ItemScore.objects.bulk_update(updated_item_scores, ['score', 'max_points'])

    # ── Step 2: Recompute StationScore totals for the whole station ──────
    station = instance.station
    new_station_max = station.get_max_score()

    station_scores = list(StationScore.objects.filter(station=station).prefetch_related('item_scores'))
    updated_station_scores = []
    for ss in station_scores:
        ss.total_score = round(sum(i.score or 0 for i in ss.item_scores.all()), 2)
        ss.max_score = new_station_max
        if new_station_max and new_station_max > 0:
            ss.percentage = round((ss.total_score / new_station_max) * 100, 2)
        else:
            ss.percentage = 0
        updated_station_scores.append(ss)

    if updated_station_scores:
        StationScore.objects.bulk_update(updated_station_scores, ['total_score', 'max_score', 'percentage'])
        logger.info(
            'CHECKLIST_CHANGE | station=%s | rubric=%s | new_item_points=%s | new_station_max=%s '
            '| item_scores_updated=%d | station_scores_updated=%d',
            station.id, instance.rubric_type, new_item_points, new_station_max,
            len(updated_item_scores), len(updated_station_scores),
        )
