"""
AuditLog model – records every significant action in the system.

Provides:
  - 37 action-type constants (authentication, CRUD, scoring, reports, admin)
  - Status constants (SUCCESS / BLOCKED / FAILED)
  - Full old_value / new_value JSON diff for UPDATE actions
  - Department scoping for coordinator-level log access
"""
from django.conf import settings
from django.db import models


# ═══════════════════════════════════════════════════════════════════
# ACTION TYPE CONSTANTS
# ═══════════════════════════════════════════════════════════════════

# Authentication
LOGIN_SUCCESS             = 'LOGIN_SUCCESS'
LOGIN_FAILED              = 'LOGIN_FAILED'
LOGOUT                    = 'LOGOUT'
PASSWORD_CHANGED          = 'PASSWORD_CHANGED'
PASSWORD_RESET            = 'PASSWORD_RESET'
SESSION_EXPIRED           = 'SESSION_EXPIRED'

# Department
DEPT_CREATED              = 'DEPT_CREATED'
DEPT_UPDATED              = 'DEPT_UPDATED'
DEPT_DELETED              = 'DEPT_DELETED'
COORDINATOR_ASSIGNED      = 'COORDINATOR_ASSIGNED'
COORDINATOR_REMOVED       = 'COORDINATOR_REMOVED'

# Course
COURSE_CREATED            = 'COURSE_CREATED'
COURSE_UPDATED            = 'COURSE_UPDATED'
COURSE_DELETED            = 'COURSE_DELETED'

# Exam
EXAM_CREATED              = 'EXAM_CREATED'
EXAM_UPDATED              = 'EXAM_UPDATED'
EXAM_DELETED              = 'EXAM_DELETED'
EXAM_PUBLISHED            = 'EXAM_PUBLISHED'

# Session
SESSION_CREATED           = 'SESSION_CREATED'
SESSION_UPDATED           = 'SESSION_UPDATED'
SESSION_DELETED           = 'SESSION_DELETED'
SESSION_STATUS_CHANGED    = 'SESSION_STATUS_CHANGED'

# Path
PATH_CREATED              = 'PATH_CREATED'
PATH_UPDATED              = 'PATH_UPDATED'
PATH_DELETED              = 'PATH_DELETED'

# Station
STATION_CREATED           = 'STATION_CREATED'
STATION_UPDATED           = 'STATION_UPDATED'
STATION_DELETED           = 'STATION_DELETED'
STATION_ACCESSED          = 'STATION_ACCESSED'

# Checklist
CHECKLIST_CREATED         = 'CHECKLIST_CREATED'
CHECKLIST_UPDATED         = 'CHECKLIST_UPDATED'
CHECKLIST_DELETED         = 'CHECKLIST_DELETED'

# Scoring
SCORE_SUBMITTED           = 'SCORE_SUBMITTED'
SCORE_AMENDED             = 'SCORE_AMENDED'

# Examiner assignment
EXAMINER_ASSIGNED         = 'EXAMINER_ASSIGNED'
EXAMINER_UNASSIGNED       = 'EXAMINER_UNASSIGNED'
EXAMINER_ACCESS_BLOCKED   = 'EXAMINER_ACCESS_BLOCKED'

# Reports & export
REPORT_VIEWED             = 'REPORT_VIEWED'
REPORT_EXPORTED           = 'REPORT_EXPORTED'

# Admin & security
ADMIN_ACTION              = 'ADMIN_ACTION'
UNAUTHORIZED_ACCESS       = 'UNAUTHORIZED_ACCESS'

# All choices for the model field
ACTION_TYPE_CHOICES = [
    # Auth
    (LOGIN_SUCCESS,           'Login Success'),
    (LOGIN_FAILED,            'Login Failed'),
    (LOGOUT,                  'Logout'),
    (PASSWORD_CHANGED,        'Password Changed'),
    (PASSWORD_RESET,          'Password Reset'),
    (SESSION_EXPIRED,         'Session Expired'),
    # Department
    (DEPT_CREATED,            'Department Created'),
    (DEPT_UPDATED,            'Department Updated'),
    (DEPT_DELETED,            'Department Deleted'),
    (COORDINATOR_ASSIGNED,    'Coordinator Assigned'),
    (COORDINATOR_REMOVED,     'Coordinator Removed'),
    # Course
    (COURSE_CREATED,          'Course Created'),
    (COURSE_UPDATED,          'Course Updated'),
    (COURSE_DELETED,          'Course Deleted'),
    # Exam
    (EXAM_CREATED,            'Exam Created'),
    (EXAM_UPDATED,            'Exam Updated'),
    (EXAM_DELETED,            'Exam Deleted'),
    (EXAM_PUBLISHED,          'Exam Published'),
    # Session
    (SESSION_CREATED,         'Session Created'),
    (SESSION_UPDATED,         'Session Updated'),
    (SESSION_DELETED,         'Session Deleted'),
    (SESSION_STATUS_CHANGED,  'Session Status Changed'),
    # Path
    (PATH_CREATED,            'Path Created'),
    (PATH_UPDATED,            'Path Updated'),
    (PATH_DELETED,            'Path Deleted'),
    # Station
    (STATION_CREATED,         'Station Created'),
    (STATION_UPDATED,         'Station Updated'),
    (STATION_DELETED,         'Station Deleted'),
    (STATION_ACCESSED,        'Station Accessed'),
    # Checklist
    (CHECKLIST_CREATED,       'Checklist Created'),
    (CHECKLIST_UPDATED,       'Checklist Updated'),
    (CHECKLIST_DELETED,       'Checklist Deleted'),
    # Scoring
    (SCORE_SUBMITTED,         'Score Submitted'),
    (SCORE_AMENDED,           'Score Amended'),
    # Examiner assignment
    (EXAMINER_ASSIGNED,       'Examiner Assigned'),
    (EXAMINER_UNASSIGNED,     'Examiner Unassigned'),
    (EXAMINER_ACCESS_BLOCKED, 'Examiner Access Blocked'),
    # Reports
    (REPORT_VIEWED,           'Report Viewed'),
    (REPORT_EXPORTED,         'Report Exported'),
    # Admin
    (ADMIN_ACTION,            'Admin Action'),
    (UNAUTHORIZED_ACCESS,     'Unauthorized Access Attempt'),
]

# Status constants
STATUS_SUCCESS = 'SUCCESS'
STATUS_BLOCKED = 'BLOCKED'
STATUS_FAILED  = 'FAILED'

STATUS_CHOICES = [
    (STATUS_SUCCESS, 'Success'),
    (STATUS_BLOCKED, 'Blocked'),
    (STATUS_FAILED,  'Failed'),
]


# ═══════════════════════════════════════════════════════════════════
# AUDIT LOG MODEL
# ═══════════════════════════════════════════════════════════════════

class AuditLog(models.Model):
    """
    Immutable audit record for every significant action.

    Records are never edited or deleted via the application.
    Old records can be archived via the archive_old_logs management command.
    """

    id = models.BigAutoField(primary_key=True, editable=False)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        help_text='Authenticated user who performed the action',
    )
    username = models.CharField(
        max_length=150, blank=True, default='',
        help_text='Snapshot of username at action time',
    )
    user_role = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Role snapshot (examiner/coordinator/admin/superuser)',
    )

    # Department scoping (for coordinator-level access control)
    department_id = models.IntegerField(
        null=True, blank=True, db_index=True,
        help_text='Department ID for scoped access (nullable)',
    )

    # What happened
    action = models.CharField(
        max_length=30, choices=ACTION_TYPE_CHOICES, db_index=True,
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_SUCCESS,
    )

    # What was affected
    resource_type = models.CharField(max_length=50, db_index=True)
    resource_id = models.CharField(max_length=36, blank=True, default='')
    resource_label = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Human-readable name of the affected object',
    )

    # Change tracking
    old_value = models.JSONField(
        null=True, blank=True,
        help_text='Previous state (for updates/deletes)',
    )
    new_value = models.JSONField(
        null=True, blank=True,
        help_text='New state (for creates/updates)',
    )

    # Description
    description = models.TextField(blank=True, default='')

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    request_method = models.CharField(max_length=10, blank=True, default='')
    request_path = models.CharField(max_length=500, blank=True, default='')

    # Extra context (JSON)
    extra_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['user', 'action'], name='idx_audit_user_action'),
            models.Index(fields=['resource_type', 'resource_id'], name='idx_audit_resource'),
            models.Index(fields=['department_id', 'timestamp'], name='idx_audit_dept_ts'),
            models.Index(fields=['action', 'timestamp'], name='idx_audit_action_ts'),
            models.Index(fields=['status', 'timestamp'], name='idx_audit_status_ts'),
        ]

    def __str__(self):
        ts = self.timestamp.strftime('%Y-%m-%d %H:%M') if self.timestamp else '?'
        role = f'[{self.user_role}]' if self.user_role else ''
        return (
            f'[{ts}] {role} {self.username} did {self.action} '
            f'on {self.resource_type}:{self.resource_label}'
        )


class AuditLogArchive(models.Model):
    """
    Archive table for old audit logs.
    Same schema as AuditLog — records are moved here by the
    archive_old_logs management command (never deleted).
    """

    id = models.BigIntegerField(primary_key=True, editable=False)

    timestamp = models.DateTimeField(db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_log_archives',
    )
    username = models.CharField(max_length=150, blank=True, default='')
    user_role = models.CharField(max_length=30, blank=True, default='')
    department_id = models.IntegerField(null=True, blank=True, db_index=True)

    action = models.CharField(max_length=30, db_index=True)
    status = models.CharField(max_length=10, default=STATUS_SUCCESS)

    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=36, blank=True, default='')
    resource_label = models.CharField(max_length=200, blank=True, default='')

    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)

    description = models.TextField(blank=True, default='')

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    request_method = models.CharField(max_length=10, blank=True, default='')
    request_path = models.CharField(max_length=500, blank=True, default='')

    extra_data = models.JSONField(null=True, blank=True)

    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs_archive'
        ordering = ['-timestamp']
        verbose_name = 'Audit Log (Archived)'
        verbose_name_plural = 'Audit Logs (Archived)'
