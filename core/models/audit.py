"""
AuditLog model – records every significant action in the system.

Provides:
  - 87 action-type constants (auth, CRUD, scoring, grading, reports, admin)
  - Status constants (SUCCESS / BLOCKED / FAILED / PARTIAL)
  - Full old_value / new_value JSON diff for UPDATE actions
  - SHA-256 checksum for tamper detection
  - Department scoping for coordinator-level log access
  - Immutability enforcement at Django + DB level
"""
import hashlib
import json as _json

from django.conf import settings
from django.db import models


# ═══════════════════════════════════════════════════════════════════
# ACTION TYPE CONSTANTS  (87 total)
# ═══════════════════════════════════════════════════════════════════

# Authentication (6)
LOGIN_SUCCESS             = 'LOGIN_SUCCESS'
LOGIN_FAILED              = 'LOGIN_FAILED'
LOGOUT                    = 'LOGOUT'
PASSWORD_CHANGED          = 'PASSWORD_CHANGED'
PASSWORD_RESET            = 'PASSWORD_RESET'
SESSION_EXPIRED           = 'SESSION_EXPIRED'

# Department (5)
DEPT_CREATED              = 'DEPT_CREATED'
DEPT_UPDATED              = 'DEPT_UPDATED'
DEPT_DELETED              = 'DEPT_DELETED'
COORDINATOR_ASSIGNED      = 'COORDINATOR_ASSIGNED'
COORDINATOR_REMOVED       = 'COORDINATOR_REMOVED'

# Course (3)
COURSE_CREATED            = 'COURSE_CREATED'
COURSE_UPDATED            = 'COURSE_UPDATED'
COURSE_DELETED            = 'COURSE_DELETED'

# Exam (4)
EXAM_CREATED              = 'EXAM_CREATED'
EXAM_UPDATED              = 'EXAM_UPDATED'
EXAM_DELETED              = 'EXAM_DELETED'
EXAM_PUBLISHED            = 'EXAM_PUBLISHED'

# Session (4)
SESSION_CREATED           = 'SESSION_CREATED'
SESSION_UPDATED           = 'SESSION_UPDATED'
SESSION_DELETED           = 'SESSION_DELETED'
SESSION_STATUS_CHANGED    = 'SESSION_STATUS_CHANGED'

# Path (3)
PATH_CREATED              = 'PATH_CREATED'
PATH_UPDATED              = 'PATH_UPDATED'
PATH_DELETED              = 'PATH_DELETED'

# Station (4)
STATION_CREATED           = 'STATION_CREATED'
STATION_UPDATED           = 'STATION_UPDATED'
STATION_DELETED           = 'STATION_DELETED'
STATION_ACCESSED          = 'STATION_ACCESSED'

# Checklist (3)
CHECKLIST_CREATED         = 'CHECKLIST_CREATED'
CHECKLIST_UPDATED         = 'CHECKLIST_UPDATED'
CHECKLIST_DELETED         = 'CHECKLIST_DELETED'

# Scoring & Grading (8)
SCORE_SUBMITTED           = 'SCORE_SUBMITTED'
SCORE_UPDATED             = 'SCORE_UPDATED'
SCORE_AMENDED             = 'SCORE_AMENDED'
SCORE_BULK_SUBMITTED      = 'SCORE_BULK_SUBMITTED'
GRADING_SESSION_STARTED   = 'GRADING_SESSION_STARTED'
GRADING_SESSION_COMPLETED = 'GRADING_SESSION_COMPLETED'
GRADING_SESSION_ABANDONED = 'GRADING_SESSION_ABANDONED'
CHECKLIST_SCORE_DELETED   = 'CHECKLIST_SCORE_DELETED'

# Examiner assignment (3)
EXAMINER_ASSIGNED         = 'EXAMINER_ASSIGNED'
EXAMINER_UNASSIGNED       = 'EXAMINER_UNASSIGNED'
EXAMINER_ACCESS_BLOCKED   = 'EXAMINER_ACCESS_BLOCKED'

# Reports & export (2)
REPORT_VIEWED             = 'REPORT_VIEWED'
REPORT_EXPORTED           = 'REPORT_EXPORTED'

# Student management (4)
STUDENT_ADDED             = 'STUDENT_ADDED'
STUDENT_REMOVED           = 'STUDENT_REMOVED'
STUDENT_PATH_ASSIGNED     = 'STUDENT_PATH_ASSIGNED'
STUDENT_BULK_IMPORT       = 'STUDENT_BULK_IMPORT'

# Examiner management (5)
EXAMINER_CREATED          = 'EXAMINER_CREATED'
EXAMINER_UPDATED          = 'EXAMINER_UPDATED'
EXAMINER_DELETED          = 'EXAMINER_DELETED'
EXAMINER_RESTORED         = 'EXAMINER_RESTORED'
EXAMINER_BULK_IMPORT      = 'EXAMINER_BULK_IMPORT'

# Template management (4)
TEMPLATE_CREATED          = 'TEMPLATE_CREATED'
TEMPLATE_UPDATED          = 'TEMPLATE_UPDATED'
TEMPLATE_DELETED          = 'TEMPLATE_DELETED'
TEMPLATE_APPLIED          = 'TEMPLATE_APPLIED'

# Session lifecycle (6)
SESSION_ACTIVATED         = 'SESSION_ACTIVATED'
SESSION_DEACTIVATED       = 'SESSION_DEACTIVATED'
SESSION_FINISHED          = 'SESSION_FINISHED'
SESSION_COMPLETED         = 'SESSION_COMPLETED'
SESSION_RESTORED          = 'SESSION_RESTORED'
SESSION_REVERTED          = 'SESSION_REVERTED'

# Exam lifecycle (4)
EXAM_COMPLETED            = 'EXAM_COMPLETED'
EXAM_REVERTED             = 'EXAM_REVERTED'
EXAM_ARCHIVED             = 'EXAM_ARCHIVED'
EXAM_RESTORED             = 'EXAM_RESTORED'

# Verification events (4)
EXAM_START_VERIFICATION_ATTEMPT   = 'EXAM_START_VERIFY_ATT'
EXAM_START_VERIFICATION_SUCCESS   = 'EXAM_START_VERIFY_OK'
MASTER_KEY_VERIFICATION_ATTEMPT   = 'MASTER_KEY_VERIFY_ATT'
MASTER_KEY_VERIFICATION_SUCCESS   = 'MASTER_KEY_VERIFY_OK'

# Audit system self-logging (3)
AUDIT_LOG_VIEWED          = 'AUDIT_LOG_VIEWED'
AUDIT_LOG_SEARCHED        = 'AUDIT_LOG_SEARCHED'
AUDIT_LOG_EXPORTED        = 'AUDIT_LOG_EXPORTED'

# Data operations (2)
BULK_OPERATION            = 'BULK_OPERATION'
DATA_EXPORT               = 'DATA_EXPORT'

# Admin & security (5)
ADMIN_ACTION              = 'ADMIN_ACTION'
UNAUTHORIZED_ACCESS       = 'UNAUTHORIZED_ACCESS'
SUSPICIOUS_ACTIVITY       = 'SUSPICIOUS_ACTIVITY'
RATE_LIMIT_HIT            = 'RATE_LIMIT_HIT'
TOKEN_VALIDATION_FAILED   = 'TOKEN_VALIDATION_FAILED'

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
    # Scoring & Grading
    (SCORE_SUBMITTED,         'Score Submitted'),
    (SCORE_UPDATED,           'Score Updated'),
    (SCORE_AMENDED,           'Score Amended'),
    (SCORE_BULK_SUBMITTED,    'Score Bulk Submitted'),
    (GRADING_SESSION_STARTED,   'Grading Session Started'),
    (GRADING_SESSION_COMPLETED, 'Grading Session Completed'),
    (GRADING_SESSION_ABANDONED, 'Grading Session Abandoned'),
    (CHECKLIST_SCORE_DELETED,   'Checklist Score Deleted'),
    # Examiner assignment
    (EXAMINER_ASSIGNED,       'Examiner Assigned'),
    (EXAMINER_UNASSIGNED,     'Examiner Unassigned'),
    (EXAMINER_ACCESS_BLOCKED, 'Examiner Access Blocked'),
    # Reports
    (REPORT_VIEWED,           'Report Viewed'),
    (REPORT_EXPORTED,         'Report Exported'),
    # Student management
    (STUDENT_ADDED,           'Student Added'),
    (STUDENT_REMOVED,         'Student Removed'),
    (STUDENT_PATH_ASSIGNED,   'Student Path Assigned'),
    (STUDENT_BULK_IMPORT,     'Student Bulk Import'),
    # Examiner management
    (EXAMINER_CREATED,        'Examiner Created'),
    (EXAMINER_UPDATED,        'Examiner Updated'),
    (EXAMINER_DELETED,        'Examiner Deleted'),
    (EXAMINER_RESTORED,       'Examiner Restored'),
    (EXAMINER_BULK_IMPORT,    'Examiner Bulk Import'),
    # Template management
    (TEMPLATE_CREATED,        'Template Created'),
    (TEMPLATE_UPDATED,        'Template Updated'),
    (TEMPLATE_DELETED,        'Template Deleted'),
    (TEMPLATE_APPLIED,        'Template Applied'),
    # Session lifecycle
    (SESSION_ACTIVATED,       'Session Activated'),
    (SESSION_DEACTIVATED,     'Session Deactivated'),
    (SESSION_FINISHED,        'Session Finished'),
    (SESSION_COMPLETED,       'Session Completed'),
    (SESSION_RESTORED,        'Session Restored'),
    (SESSION_REVERTED,        'Session Reverted'),
    # Exam lifecycle
    (EXAM_COMPLETED,          'Exam Completed'),
    (EXAM_REVERTED,           'Exam Reverted'),
    (EXAM_ARCHIVED,           'Exam Archived'),
    (EXAM_RESTORED,           'Exam Restored'),
    # Verification events
    (EXAM_START_VERIFICATION_ATTEMPT, 'Exam Start Verification Attempt'),
    (EXAM_START_VERIFICATION_SUCCESS, 'Exam Start Verification Success'),
    (MASTER_KEY_VERIFICATION_ATTEMPT, 'Master Key Verification Attempt'),
    (MASTER_KEY_VERIFICATION_SUCCESS, 'Master Key Verification Success'),
    # Audit self-logging
    (AUDIT_LOG_VIEWED,        'Audit Log Viewed'),
    (AUDIT_LOG_SEARCHED,      'Audit Log Searched'),
    (AUDIT_LOG_EXPORTED,      'Audit Log Exported'),
    # Data operations
    (BULK_OPERATION,          'Bulk Operation'),
    (DATA_EXPORT,             'Data Export'),
    # Admin & security
    (ADMIN_ACTION,            'Admin Action'),
    (UNAUTHORIZED_ACCESS,     'Unauthorized Access Attempt'),
    (SUSPICIOUS_ACTIVITY,     'Suspicious Activity'),
    (RATE_LIMIT_HIT,          'Rate Limit Hit'),
    (TOKEN_VALIDATION_FAILED, 'Token Validation Failed'),
]

# Status constants
STATUS_SUCCESS = 'SUCCESS'
STATUS_BLOCKED = 'BLOCKED'
STATUS_FAILED  = 'FAILED'
STATUS_PARTIAL = 'PARTIAL'

STATUS_CHOICES = [
    (STATUS_SUCCESS, 'Success'),
    (STATUS_BLOCKED, 'Blocked'),
    (STATUS_FAILED,  'Failed'),
    (STATUS_PARTIAL, 'Partial'),
]


# ═══════════════════════════════════════════════════════════════════
# CHECKSUM HELPER
# ═══════════════════════════════════════════════════════════════════

def compute_checksum(user_id, action, resource_id, timestamp, old_value, new_value):
    """Compute SHA-256 checksum over the core audit fields."""
    ts_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp or '')
    old_str = _json.dumps(old_value, sort_keys=True, default=str) if old_value else ''
    new_str = _json.dumps(new_value, sort_keys=True, default=str) if new_value else ''
    payload = f'{user_id}{action}{resource_id}{ts_str}{old_str}{new_str}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


# ═══════════════════════════════════════════════════════════════════
# AUDIT LOG MODEL
# ═══════════════════════════════════════════════════════════════════

class AuditLog(models.Model):
    """
    Immutable audit record for every significant action.

    Records are never edited or deleted via the application.
    Old records can be archived via the archive_old_logs management command.
    Tamper detection via SHA-256 checksum on core fields.
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

    # Tamper detection
    checksum = models.CharField(
        max_length=64, blank=True, default='',
        editable=False,
        help_text='SHA-256 checksum for tamper detection',
    )

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        default_permissions = ('add', 'view')  # No change/delete
        indexes = [
            models.Index(fields=['user', 'action'], name='idx_audit_user_action'),
            models.Index(fields=['resource_type', 'resource_id'], name='idx_audit_resource'),
            models.Index(fields=['department_id', 'timestamp'], name='idx_audit_dept_ts'),
            models.Index(fields=['action', 'timestamp'], name='idx_audit_action_ts'),
            models.Index(fields=['status', 'timestamp'], name='idx_audit_status_ts'),
        ]

    def save(self, *args, **kwargs):
        needs_checksum = not self.checksum
        super().save(*args, **kwargs)
        # Compute checksum AFTER super().save() so auto_now_add has set
        # self.timestamp before we hash it. Use a direct UPDATE to avoid
        # a recursive save() call.
        if needs_checksum:
            self.checksum = compute_checksum(
                self.user_id, self.action, self.resource_id,
                self.timestamp, self.old_value, self.new_value,
            )
            type(self).objects.filter(pk=self.pk).update(checksum=self.checksum)

    def verify_checksum(self):
        """Return True if the stored checksum matches the recomputed value."""
        expected = compute_checksum(
            self.user_id, self.action, self.resource_id,
            self.timestamp, self.old_value, self.new_value,
        )
        return self.checksum == expected

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

    checksum = models.CharField(max_length=64, blank=True, default='')

    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs_archive'
        ordering = ['-timestamp']
        verbose_name = 'Audit Log (Archived)'
        verbose_name_plural = 'Audit Logs (Archived)'
        default_permissions = ('add', 'view')  # No change/delete
