"""
Checklist Library model – reusable checklist items.
"""
from django.db import models
from .mixins import TimestampMixin


class ChecklistLibrary(TimestampMixin):
    """Library of reusable checklist items mapped to ILOs."""

    id = models.AutoField(primary_key=True)
    ilo = models.ForeignKey(
        'core.ILO', on_delete=models.CASCADE, related_name='library_items', db_index=True
    )

    description = models.TextField()
    suggested_points = models.FloatField(default=1)
    is_critical = models.BooleanField(default=False)

    rubric_type = models.CharField(max_length=20, default='binary')
    interaction_type = models.CharField(max_length=20, default='passive')
    expected_response = models.TextField(blank=True, default='')

    usage_count = models.IntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = 'checklist_library'
        indexes = [
            models.Index(fields=['ilo', 'active'], name='idx_library_ilo_active'),
        ]

    def __str__(self):
        return f'LibraryItem {self.id}: {self.description[:40]}'

    def increment_usage(self):
        self.usage_count = (self.usage_count or 0) + 1
        self.save(update_fields=['usage_count'])

    def to_dict(self):
        return {
            'id': self.id,
            'ilo_id': self.ilo_id,
            'description': self.description,
            'suggested_points': self.suggested_points,
            'is_critical': self.is_critical,
            'rubric_type': self.rubric_type,
            'interaction_type': self.interaction_type,
            'expected_response': self.expected_response,
            'usage_count': self.usage_count or 0,
            'active': self.active,
            'theme_id': self.ilo.theme_id if self.ilo else None,
            'theme_name': self.ilo.theme.name if self.ilo and self.ilo.theme else None,
            'theme_color': self.ilo.theme.color if self.ilo and self.ilo.theme else '#6c757d',
        }
