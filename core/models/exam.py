"""
Exam, Station, and ChecklistItem models.
"""
import uuid
from datetime import datetime, timezone
from django.db import models
from .mixins import TimestampMixin


class Exam(TimestampMixin):
    """OSCE Examination instance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        'core.Course', on_delete=models.CASCADE, related_name='exams', db_index=True
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    exam_date = models.DateField()
    department = models.CharField(max_length=100, blank=True, default='')

    number_of_stations = models.IntegerField(default=4)
    station_duration_minutes = models.IntegerField(default=8)
    exam_weight = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        help_text='Final grade weight (e.g. 40 means the exam is marked out of 40 regardless of total station marks)'
    )

    # Status: draft, ready, in_progress, completed, archived
    status = models.CharField(max_length=20, default='draft')

    # Soft delete
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.IntegerField(null=True, blank=True)
    deleted_by = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'exams'

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    @classmethod
    def active_objects(cls):
        return cls.objects.filter(is_deleted=False)

    def soft_delete(self, user_id=None):
        self.is_deleted = True
        self.deleted_at = int(datetime.now(timezone.utc).timestamp())
        self.deleted_by = user_id
        self.status = 'archived'
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.status = 'draft'
        self.save()

    def get_total_marks(self):
        total = 0
        for station in self.stations.all():
            total += sum(item.points for item in station.checklist_items.all())
        return total

    def get_ilo_distribution(self):
        distribution = {}
        for station in self.stations.all():
            for item in station.checklist_items.all():
                ilo_id = item.ilo_id
                distribution[ilo_id] = distribution.get(ilo_id, 0) + item.points
        return distribution

    def validate_marks(self):
        from .course import ILO
        errors = []
        distribution = self.get_ilo_distribution()
        ilos = ILO.objects.filter(course_id=self.course_id)
        for ilo in ilos:
            if not ilo.osce_marks:
                continue
            used = distribution.get(ilo.id, 0)
            if used > ilo.osce_marks:
                errors.append(
                    f"ILO #{ilo.number}: Uses {used} marks but only {ilo.osce_marks} allocated"
                )
        return errors

    def to_dict(self, include_stations=False):
        data = {
            'id': str(self.id),
            'course_id': self.course_id,
            'name': self.name,
            'description': self.description,
            'exam_date': self.exam_date.isoformat() if self.exam_date else None,
            'status': self.status,
            'total_marks': self.get_total_marks(),
            'station_count': self.stations.count(),
        }
        if include_stations:
            data['stations'] = [s.to_dict() for s in self.stations.all()]
        return data


class Station(TimestampMixin):
    """Individual station within an OSCE path."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    path = models.ForeignKey(
        'core.Path', on_delete=models.CASCADE, null=True, blank=True,
        related_name='stations', db_index=True
    )
    # Legacy FK kept for migration compatibility
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, null=True, blank=True,
        related_name='stations', db_index=True
    )

    station_number = models.IntegerField()
    name = models.CharField(max_length=100)

    scenario = models.TextField(blank=True, default='')
    instructions = models.TextField(blank=True, default='')

    duration_minutes = models.IntegerField(default=8)
    active = models.BooleanField(default=True, db_index=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'stations'
        ordering = ['station_number']
        constraints = [
            models.UniqueConstraint(
                fields=['path', 'station_number'],
                name='unique_path_station'
            ),
        ]
        indexes = [
            models.Index(fields=['path', 'active'], name='idx_station_path_active'),
        ]

    def __str__(self):
        return f'Station {self.station_number}: {self.name}'

    # Properties
    @property
    def session(self):
        return self.path.session if self.path else None

    @property
    def exam_via_path(self):
        if self.path and self.path.session:
            return self.path.session.exam
        return self.exam

    @property
    def parent_exam(self):
        return self.exam_via_path

    # Query helpers
    @classmethod
    def active_objects(cls):
        return cls.objects.filter(active=True, is_deleted=False)

    def soft_delete(self):
        self.is_deleted = True
        self.active = False
        self.deleted_at = int(datetime.now(timezone.utc).timestamp())
        self.save()

    def restore(self):
        self.is_deleted = False
        self.active = True
        self.deleted_at = None
        self.save()

    def get_max_score(self):
        return sum(item.points for item in self.checklist_items.all())

    def get_critical_items(self):
        return list(self.checklist_items.filter(is_critical=True))

    def to_dict(self, include_items=False):
        data = {
            'id': str(self.id),
            'path_id': str(self.path_id) if self.path_id else None,
            'exam_id': str(self.exam_id) if self.exam_id else None,
            'station_number': self.station_number,
            'name': self.name,
            'scenario': self.scenario,
            'instructions': self.instructions,
            'duration_minutes': self.duration_minutes,
            'active': self.active,
            'is_deleted': self.is_deleted,
            'max_score': self.get_max_score(),
            'item_count': self.checklist_items.count(),
        }
        if include_items:
            data['checklist_items'] = [item.to_dict() for item in self.checklist_items.all()]
        return data


class ChecklistItem(TimestampMixin):
    """Individual checklist item for scoring at a station."""

    id = models.AutoField(primary_key=True)
    station = models.ForeignKey(
        Station, on_delete=models.CASCADE, related_name='checklist_items', db_index=True
    )
    library_item = models.ForeignKey(
        'core.ChecklistLibrary', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='station_items'
    )
    ilo = models.ForeignKey(
        'core.ILO', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_items', db_index=True
    )

    item_number = models.IntegerField()
    description = models.TextField()
    points = models.IntegerField(default=1)
    category = models.CharField(max_length=50, blank=True, default='')
    is_critical = models.BooleanField(default=False)

    # Rubric: binary, partial, scale
    rubric_type = models.CharField(max_length=20, default='binary')
    rubric_levels = models.JSONField(null=True, blank=True)

    # Interaction type
    interaction_type = models.CharField(max_length=20, default='passive')
    expected_response = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'checklist_items'
        ordering = ['item_number']
        constraints = [
            models.UniqueConstraint(
                fields=['station', 'item_number'],
                name='unique_station_item'
            ),
        ]
        indexes = [
            models.Index(fields=['ilo'], name='idx_item_ilo'),
        ]

    def __str__(self):
        return f'Item {self.item_number}: {self.description[:40]}'

    def to_dict(self):
        return {
            'id': self.id,
            'station_id': str(self.station_id),
            'library_item_id': self.library_item_id,
            'ilo_id': self.ilo_id,
            'item_number': self.item_number,
            'description': self.description,
            'points': self.points,
            'category': self.category,
            'is_critical': self.is_critical,
            'rubric_type': self.rubric_type,
            'rubric_levels': self.rubric_levels,
            'interaction_type': self.interaction_type,
            'expected_response': self.expected_response,
        }
