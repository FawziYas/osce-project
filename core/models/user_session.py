"""
UserSession model — tracks one active session per user.

Used to enforce the single-active-login policy:
a new login is blocked if a valid session already exists for that user.
Superusers can delete records via Django Admin to free stuck sessions.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


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
        """
        Check that the session key still exists and has not expired.

        store.exists() on Django's DB backend only checks row presence — it does
        NOT filter by expire_date.  Expired rows linger until clearsessions runs,
        which caused the single-session block to never lift on its own locally.

        Fix: for DB-backed sessions query the expire_date explicitly; for cache
        backends (which auto-evict) fall back to exists() which is reliable there.
        """
        from importlib import import_module
        from django.utils import timezone

        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore()

        # Fast path: row/key doesn't exist at all
        if not store.exists(self.session_key):
            return False

        # For DB backends the row may exist but be logically expired — check that
        try:
            from django.contrib.sessions.models import Session as DjSession
            return DjSession.objects.filter(
                session_key=self.session_key,
                expire_date__gt=timezone.now(),
            ).exists()
        except Exception:
            # Cache / cached_db backends don't use Session model; exists() is enough
            return True
