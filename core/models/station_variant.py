"""
Station Variant model – session-specific overrides for stations.
"""
from django.db import models
from .mixins import TimestampMixin


class StationVariant(TimestampMixin):
    """Override/variant of a station for a specific exam session."""

    id = models.AutoField(primary_key=True)
    station = models.ForeignKey(
        'core.Station', on_delete=models.CASCADE,
        related_name='session_variants', db_index=True
    )
    exam_session = models.ForeignKey(
        'core.ExamSession', on_delete=models.CASCADE,
        related_name='station_variants', db_index=True
    )

    scenario_override = models.TextField(blank=True, default='')
    instructions_override = models.TextField(blank=True, default='')
    duration_minutes_override = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'station_variants'
        constraints = [
            models.UniqueConstraint(
                fields=['station', 'exam_session'],
                name='unique_station_session_variant'
            ),
        ]
        indexes = [
            models.Index(fields=['exam_session'], name='idx_variant_session'),
        ]

    def __str__(self):
        return f'StationVariant Station{self.station_id} Session{self.exam_session_id}'

    def get_scenario(self):
        if self.scenario_override:
            return self.scenario_override
        return self.station.scenario if self.station else None

    def get_instructions(self):
        if self.instructions_override:
            return self.instructions_override
        return self.station.instructions if self.station else None

    def get_duration(self):
        if self.duration_minutes_override:
            return self.duration_minutes_override
        return self.station.duration_minutes if self.station else 8

    def to_dict(self):
        return {
            'id': self.id,
            'station_id': str(self.station_id),
            'exam_session_id': str(self.exam_session_id),
            'scenario_override': self.scenario_override,
            'instructions_override': self.instructions_override,
            'duration_minutes_override': self.duration_minutes_override,
            'notes': self.notes,
            'has_scenario_override': bool(self.scenario_override),
            'has_instructions_override': bool(self.instructions_override),
            'has_duration_override': bool(self.duration_minutes_override),
        }
