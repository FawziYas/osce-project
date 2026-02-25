"""
Session and SessionStudent models.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from .mixins import TimestampMixin


def validate_student_number(value):
    """Validate that student number contains only digits."""
    if not value.isdigit():
        raise ValidationError('Registration number must contain numbers only.')


class ExamSession(models.Model):
    """A specific instance of an OSCE exam being administered."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(
        'core.Exam', on_delete=models.CASCADE, related_name='sessions', db_index=True
    )

    name = models.CharField(max_length=100)

    session_date = models.DateField()
    session_type = models.CharField(max_length=20, default='morning')
    start_time = models.TimeField()

    number_of_stations = models.IntegerField()
    number_of_paths = models.IntegerField()

    # Status: scheduled, in_progress, completed, cancelled
    status = models.CharField(max_length=20, default='scheduled')

    actual_start = models.IntegerField(null=True, blank=True)
    actual_end = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True, default='')
    created_by = models.IntegerField(null=True, blank=True)

    created_at = models.IntegerField(null=True, blank=True)
    updated_at = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'exam_sessions'
        permissions = [
            ('can_revert_session', 'Can revert completed session to scheduled'),
            ('can_delete_session', 'Can archive/delete sessions'),
        ]

    def __str__(self):
        return f'{self.name} on {self.session_date}'

    def save(self, *args, **kwargs):
        now = TimestampMixin.utc_timestamp()
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now
        super().save(*args, **kwargs)

    @property
    def student_count(self):
        return self.students.count()

    @property
    def path_count(self):
        return self.paths.count()

    def to_dict(self):
        return {
            'id': str(self.id),
            'exam_id': str(self.exam_id),
            'name': self.name,
            'session_date': self.session_date.isoformat() if self.session_date else None,
            'session_type': self.session_type,
            'status': self.status,
            'student_count': self.student_count,
        }


class SessionStudent(models.Model):
    """A student registered for a specific exam session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ExamSession, on_delete=models.CASCADE, related_name='students', db_index=True
    )
    path = models.ForeignKey(
        'core.Path', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students', db_index=True
    )

    student_number = models.CharField(max_length=50, validators=[validate_student_number])
    full_name = models.CharField(max_length=150)
    photo_url = models.CharField(max_length=500, blank=True, default='')

    # Legacy
    rotation_group = models.CharField(max_length=10, blank=True, default='')
    sequence_number = models.IntegerField(null=True, blank=True)

    # Status: registered, checked_in, in_progress, completed, absent
    status = models.CharField(max_length=20, default='registered')
    checked_in_at = models.IntegerField(null=True, blank=True)
    completed_at = models.IntegerField(null=True, blank=True)

    created_at = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'session_students'
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'student_number'],
                name='unique_session_student'
            ),
        ]

    def __str__(self):
        return f'{self.student_number}: {self.full_name}'

    def save(self, *args, **kwargs):
        if self.created_at is None:
            self.created_at = TimestampMixin.utc_timestamp()
        super().save(*args, **kwargs)

    @property
    def stations_completed(self):
        return self.station_scores.filter(status='submitted').count()

    @property
    def total_score(self):
        return sum(
            s.total_score or 0
            for s in self.station_scores.filter(status='submitted')
        )

    @property
    def max_possible_score(self):
        return sum(
            s.max_score or 0
            for s in self.station_scores.filter(status='submitted')
        )
