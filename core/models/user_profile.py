"""
UserProfile model — tracks whether a user must change their default password.
"""
from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    """
    One-to-one extension for the custom User (Examiner) model.

    The must_change_password flag is True for every new user — they get the
    default password from settings.DEFAULT_USER_PASSWORD and are forced to
    set their own password on first login via the ForcePasswordChangeMiddleware.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    must_change_password = models.BooleanField(
        default=True,
        help_text='If True the user will be forced to change their password on next login.',
    )
    password_changed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp of last intentional password change.',
    )

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        status = 'must change' if self.must_change_password else 'ok'
        return f'{self.user.username} ({status})'
