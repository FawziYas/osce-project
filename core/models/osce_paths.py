"""
OSCE Exam Path, Room Assignment, and Path Student models.
"""
from django.db import models
from .mixins import TimestampMixin


class OSCEExamPath(TimestampMixin):
    """Time block during which students rotate through rooms/stations."""

    id = models.AutoField(primary_key=True)
    exam_session = models.ForeignKey(
        'core.ExamSession', on_delete=models.CASCADE,
        related_name='osce_paths', db_index=True
    )

    path_number = models.IntegerField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=8)

    # Status: pending, in_progress, completed
    status = models.CharField(max_length=20, default='pending')
    started_at = models.IntegerField(null=True, blank=True)
    completed_at = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'osce_exam_paths'
        constraints = [
            models.UniqueConstraint(
                fields=['exam_session', 'path_number'],
                name='unique_session_osce_path_number'
            ),
        ]
        indexes = [
            models.Index(
                fields=['exam_session', 'status'],
                name='idx_osce_path_session_status'
            ),
        ]

    def __str__(self):
        return f'OSCEExamPath {self.path_number}: {self.start_time}'

    @property
    def room_count(self):
        return self.room_assignments.count()

    def to_dict(self):
        return {
            'id': self.id,
            'exam_session_id': str(self.exam_session_id),
            'path_number': self.path_number,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'status': self.status,
            'room_count': self.room_count,
        }


class OSCERoomAssignment(TimestampMixin):
    """Maps a room and station to a specific OSCE exam path."""

    id = models.AutoField(primary_key=True)
    osce_path = models.ForeignKey(
        OSCEExamPath, on_delete=models.CASCADE,
        related_name='room_assignments', db_index=True
    )
    exam_session = models.ForeignKey(
        'core.ExamSession', on_delete=models.CASCADE,
        related_name='room_assignments', db_index=True
    )

    room_number = models.IntegerField()
    room_name = models.CharField(max_length=100, blank=True, default='')

    station = models.ForeignKey(
        'core.Station', on_delete=models.CASCADE,
        related_name='room_assignments', db_index=True
    )

    examiner = models.ForeignKey(
        'core.Examiner', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='room_assignments', db_index=True
    )
    examiner_name = models.CharField(max_length=200, blank=True, default='')

    status = models.CharField(max_length=20, default='pending')

    class Meta:
        db_table = 'osce_room_assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['osce_path', 'room_number'],
                name='unique_osce_path_room_number'
            ),
        ]
        indexes = [
            models.Index(
                fields=['exam_session', 'station'],
                name='idx_osce_room_session_station'
            ),
        ]

    def __str__(self):
        return f'OSCERoom {self.room_number}: Path {self.osce_path_id}'

    def to_dict(self):
        return {
            'id': self.id,
            'osce_path_id': self.osce_path_id,
            'exam_session_id': str(self.exam_session_id),
            'room_number': self.room_number,
            'room_name': self.room_name,
            'station_id': str(self.station_id),
            'examiner_id': self.examiner_id,
            'examiner_name': self.examiner_name,
            'status': self.status,
        }


class OSCEPathStudent(TimestampMixin):
    """Student assignment to specific room/path combination."""

    id = models.AutoField(primary_key=True)
    osce_path = models.ForeignKey(
        OSCEExamPath, on_delete=models.CASCADE,
        related_name='path_students', db_index=True
    )
    room_assignment = models.ForeignKey(
        OSCERoomAssignment, on_delete=models.CASCADE,
        related_name='path_students', db_index=True
    )
    student = models.ForeignKey(
        'core.Examiner', on_delete=models.CASCADE,
        related_name='osce_path_assignments', db_index=True
    )
    exam_session = models.ForeignKey(
        'core.ExamSession', on_delete=models.CASCADE,
        related_name='path_students', db_index=True
    )

    checkin_time = models.IntegerField(null=True, blank=True)
    checkout_time = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'osce_path_students'
        constraints = [
            models.UniqueConstraint(
                fields=['osce_path', 'room_assignment', 'student'],
                name='unique_osce_path_room_student'
            ),
        ]
        indexes = [
            models.Index(
                fields=['exam_session', 'student'],
                name='idx_osce_path_student_session'
            ),
        ]

    def __str__(self):
        return f'OSCEPathStudent Path{self.osce_path_id} Room{self.room_assignment_id}'

    def to_dict(self):
        return {
            'id': self.id,
            'osce_path_id': self.osce_path_id,
            'room_assignment_id': self.room_assignment_id,
            'student_id': self.student_id,
            'exam_session_id': str(self.exam_session_id),
            'checkin_time': self.checkin_time,
            'checkout_time': self.checkout_time,
        }
