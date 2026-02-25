"""
Path models – rotation tracks (A, B, C) within a session.
"""
import uuid
from datetime import datetime, timezone
from django.db import models
from .mixins import TimestampMixin


class Path(TimestampMixin):
    """
    Rotation track within an exam session.

    Students are assigned to paths (A, B, C) and rotate through
    stations that belong to this path only.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        'core.ExamSession', on_delete=models.CASCADE,
        related_name='paths', db_index=True
    )

    name = models.CharField(max_length=50)

    rotation_minutes = models.IntegerField(default=8)

    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'paths'
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'name'],
                name='unique_session_path_name_v2'
            ),
        ]
        indexes = [
            models.Index(fields=['session', 'is_active'], name='idx_path_session_active'),
        ]

    def __str__(self):
        return f'Path {self.name} in Session {self.session_id}'

    # Properties
    @property
    def station_count(self):
        return self.stations.filter(active=True).count()

    @property
    def student_count(self):
        return self.students.count()

    @property
    def total_marks(self):
        return sum(s.get_max_score() for s in self.stations.filter(active=True))

    @property
    def total_duration(self):
        return sum(s.duration_minutes or 0 for s in self.stations.filter(active=True))

    @property
    def ordered_stations(self):
        """Return stations ordered by station_number."""
        return self.stations.filter(active=True).order_by('station_number')

    @property
    def exam(self):
        return self.session.exam if self.session else None

    # Query helpers
    @classmethod
    def active_objects(cls):
        return cls.objects.filter(is_deleted=False, is_active=True)

    def get_stations_in_order(self):
        return self.stations.filter(active=True).order_by('station_number')

    # CRUD
    def soft_delete(self):
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = int(datetime.now(timezone.utc).timestamp())
        self.save()

    def restore(self):
        self.is_deleted = False
        self.is_active = True
        self.deleted_at = None
        self.save()

    def to_dict(self, include_stations=False, include_students=False):
        data = {
            'id': str(self.id),
            'session_id': str(self.session_id),
            'exam_id': str(self.session.exam_id) if self.session else None,
            'name': self.name,
            'description': self.description,
            'rotation_minutes': self.rotation_minutes,
            'station_count': self.station_count,
            'student_count': self.student_count,
            'total_marks': self.total_marks,
            'total_duration': self.total_duration,
            'is_active': self.is_active,
            'is_deleted': self.is_deleted,
        }
        if include_stations:
            data['stations'] = [
                s.to_dict() for s in self.stations.filter(active=True).order_by('station_number')
            ]
        if include_students:
            data['students'] = [
                {
                    'id': str(s.id),
                    'student_number': s.student_number,
                    'full_name': s.full_name,
                    'status': s.status,
                }
                for s in self.students.all()
            ]
        return data


# Backward-compatibility alias
StudentPath = Path


class PathStation(TimestampMixin):
    """
    DEPRECATED legacy junction table.
    Kept only for migration compatibility.
    """

    id = models.AutoField(primary_key=True)
    student_path_id = models.IntegerField(null=True, blank=True)
    path = models.ForeignKey(
        Path, on_delete=models.CASCADE, null=True, blank=True,
        related_name='legacy_path_stations'
    )
    station = models.ForeignKey(
        'core.Station', on_delete=models.CASCADE, db_index=True
    )
    sequence_order = models.IntegerField()
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'path_stations'

    def __str__(self):
        return f'PathStation {self.id}'
