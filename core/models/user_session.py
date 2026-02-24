"""
UserSession model — tracks one active session per user.

Used to enforce the single-active-login policy:
a new login is blocked if a valid session already exists for that user.
Superusers can delete records via Django Admin to free stuck sessions.
"""
from django.db import models
from django.conf import settings


class UserSession(models.Model):
    """
    Bridges Django's opaque session store to a specific user.

    OneToOne on user ensures the database itself enforces one record
    per user — no race-condition duplicates possible.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_session',
    )
    session_key = models.CharField(max_length=40, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'Active User Session'
        verbose_name_plural = 'Active User Sessions'

    def __str__(self):
        return f'{self.user.username} — {self.session_key}'

    def is_session_alive(self):
        """Check that the session key still exists in Django's session store."""
        from django.contrib.sessions.models import Session
        return Session.objects.filter(session_key=self.session_key).exists()
