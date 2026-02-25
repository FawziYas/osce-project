"""
Course and ILO models.
"""
from django.db import models
from .mixins import TimestampMixin


class Course(TimestampMixin):
    """Academic course that can have OSCE examinations."""

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=20, unique=True)
    short_code = models.CharField(max_length=20, blank=True, default='')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    year_level = models.IntegerField(default=1)

    class Meta:
        db_table = 'courses'

    def __str__(self):
        return f'{self.code}: {self.name}'

    @property
    def display_code(self):
        if self.short_code:
            return f"{self.code} ({self.short_code})"
        return self.code

    def get_total_osce_marks(self):
        return sum(ilo.osce_marks or 0 for ilo in self.ilos.all())

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'short_code': self.short_code,
            'display_code': self.display_code,
            'name': self.name,
            'description': self.description,
            'year_level': self.year_level,
            'total_osce_marks': self.get_total_osce_marks(),
            'ilo_count': self.ilos.count(),
        }


class ILO(TimestampMixin):
    """Intended Learning Outcome with OSCE mark allocation."""

    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='ilos', db_index=True
    )
    theme = models.ForeignKey(
        'core.Theme', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ilos', db_index=True
    )

    number = models.IntegerField()
    description = models.TextField()
    osce_marks = models.IntegerField(default=0)

    class Meta:
        db_table = 'ilos'
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'number'],
                name='unique_course_ilo_number'
            ),
        ]

    def __str__(self):
        theme_name = self.theme.name if self.theme else 'Unassigned'
        return f'ILO #{self.number}: {theme_name}'

    @property
    def theme_name(self):
        return self.theme.name if self.theme else 'Unassigned'

    @property
    def theme_color(self):
        return self.theme.color if self.theme else '#6c757d'

    @property
    def theme_icon(self):
        return self.theme.icon if self.theme else 'bi-circle'

    def get_used_marks(self, exclude_station_id=None):
        qs = self.checklist_items.all()
        if exclude_station_id:
            qs = qs.exclude(station_id=exclude_station_id)
        return sum(item.points for item in qs)

    def get_remaining_marks(self, exclude_station_id=None):
        return (self.osce_marks or 0) - self.get_used_marks(exclude_station_id)

    def to_dict(self, include_remaining=False, exclude_station_id=None):
        data = {
            'id': self.id,
            'course_id': self.course_id,
            'number': self.number,
            'theme_id': self.theme_id,
            'theme_name': self.theme_name,
            'theme_color': self.theme_color,
            'theme_icon': self.theme_icon,
            'description': self.description,
            'osce_marks': self.osce_marks or 0,
            'active': self.active,
        }
        if include_remaining:
            data['used_marks'] = self.get_used_marks(exclude_station_id)
            data['remaining_marks'] = self.get_remaining_marks(exclude_station_id)
        return data
