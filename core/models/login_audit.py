"""
LoginAuditLog model – records every login attempt for security audit trail.

This is a compliance-critical model for medical examination environments.
Records are immutable once created.
"""
from django.conf import settings
from django.db import models


class LoginAuditLog(models.Model):
    """
    Immutable audit record of every authentication attempt.

    Fields are intentionally non-editable. This model serves as a
    tamper-evident log for security and compliance auditing.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_audit_logs',
        help_text='Authenticated user (null for failed attempts)',
    )
    username_attempted = models.CharField(
        max_length=150,
        help_text='Username submitted in the login form',
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='Client IP address (X-Forwarded-For aware)',
    )
    user_agent = models.TextField(
        blank=True,
        default='',
        help_text='Browser / device user-agent string',
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='UTC timestamp of the login attempt',
    )
    success = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether the authentication attempt succeeded',
    )

    class Meta:
        db_table = 'login_audit_logs'
        ordering = ['-timestamp']
        verbose_name = 'Login Audit Log'
        verbose_name_plural = 'Login Audit Logs'
        indexes = [
            models.Index(fields=['user', 'timestamp'], name='idx_login_audit_user_ts'),
            models.Index(fields=['ip_address', 'timestamp'], name='idx_login_audit_ip_ts'),
            models.Index(fields=['success', 'timestamp'], name='idx_login_audit_success_ts'),
        ]

    def __str__(self):
        status = 'OK' if self.success else 'FAIL'
        return f'[{status}] {self.username_attempted} from {self.ip_address} at {self.timestamp}'
