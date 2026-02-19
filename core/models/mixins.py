"""
Base model mixins for the OSCE project.
"""
from datetime import datetime, timezone
from django.db import models


class TimestampMixin(models.Model):
    """Abstract mixin that adds integer Unix timestamp fields."""

    created_at = models.IntegerField(
        default=None, blank=True, null=True,
        help_text="UTC Unix timestamp when created"
    )
    updated_at = models.IntegerField(
        default=None, blank=True, null=True,
        help_text="UTC Unix timestamp when last updated"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        now = int(datetime.now(timezone.utc).timestamp())
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now
        super().save(*args, **kwargs)

    @staticmethod
    def utc_timestamp():
        """Get current UTC timestamp as integer."""
        return int(datetime.now(timezone.utc).timestamp())
