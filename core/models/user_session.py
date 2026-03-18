"""
UserSession model — tracks one active session per user.

Used to enforce the single-active-login policy:
a new login is blocked if a valid session already exists for that user.
Superusers can delete records via Django Admin to free stuck sessions.
"""
from importlib import import_module

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

    # ── helpers ────────────────────────────────────────────────────

    def is_session_alive(self):
        """
        Return True if the stored session_key still points to a valid,
        non-expired session — regardless of which session backend is in use.

        Strategy per backend:
        • DB backend   → store.exists() only checks row presence (ignores
                         expire_date), so we query Session.expire_date explicitly.
        • Cache backend → the cache auto-evicts expired entries, so
                         store.exists() is reliable on its own.
        • cached_db    → same as cache (primary lookup is cache).
        """
        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore()

        if not store.exists(self.session_key):
            return False

        # DB backend: exists() doesn't check expire_date — verify explicitly
        if settings.SESSION_ENGINE == 'django.contrib.sessions.backends.db':
            from django.contrib.sessions.models import Session as DjSession
            return DjSession.objects.filter(
                session_key=self.session_key,
                expire_date__gt=timezone.now(),
            ).exists()

        # Cache / cached_db / file → exists() already excludes expired entries
        return True

    def kill_session(self):
        """
        Delete both the Django session in the session store AND this
        UserSession record.  Safe to call even if the session has
        already expired or been deleted from the store.
        """
        try:
            engine = import_module(settings.SESSION_ENGINE)
            store = engine.SessionStore(session_key=self.session_key)
            store.delete()
        except Exception:
            pass
        self.delete()
