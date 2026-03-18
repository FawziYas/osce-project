"""
UserSession model — tracks active sessions per user.

Used to enforce the single-active-login policy for normal users
and to track multiple concurrent sessions for allow_multi_login users.
Superusers can delete records via Django Admin to free stuck sessions.
"""
from importlib import import_module

from django.db import models
from django.conf import settings
from django.utils import timezone


class UserSession(models.Model):
    """
    Bridges Django's opaque session store to a specific user.

    ForeignKey allows multiple records for multi-login users.
    For single-login users the login view ensures only one record exists.
    session_key is unique — one tracking row per Django session.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_sessions',
    )
    session_key = models.CharField(max_length=40, unique=True)
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
