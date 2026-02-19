"""
AuditLog model – records every significant action in the system.
"""
from django.db import models
from .mixins import TimestampMixin


class AuditLog(models.Model):
    """Records every significant action for audit trail."""

    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW', 'View'),
        ('EXPORT', 'Export'),
        ('SUBMIT', 'Submit Score'),
        ('SYNC', 'Offline Sync'),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        'core.Examiner', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    username = models.CharField(max_length=80, blank=True, default='')

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50)  # e.g. 'Exam', 'Station'
    resource_id = models.CharField(max_length=36, blank=True, default='')

    description = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    extra_data = models.JSONField(null=True, blank=True)

    timestamp = models.IntegerField(db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'action'], name='idx_audit_user_action'),
            models.Index(fields=['resource_type', 'resource_id'], name='idx_audit_resource'),
        ]

    def __str__(self):
        return f'[{self.action}] {self.username} on {self.resource_type} {self.resource_id}'

    def save(self, *args, **kwargs):
        if not self.timestamp:
            self.timestamp = TimestampMixin.utc_timestamp()
        super().save(*args, **kwargs)
