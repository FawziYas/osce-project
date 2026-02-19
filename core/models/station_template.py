"""
Station Template model – reusable station blueprints.
"""
import json
from django.db import models
from .mixins import TimestampMixin


class StationTemplate(TimestampMixin):
    """A reusable station template for an exam."""

    id = models.AutoField(primary_key=True)
    exam = models.ForeignKey(
        'core.Exam', on_delete=models.CASCADE,
        related_name='station_templates', db_index=True
    )
    library = models.ForeignKey(
        'core.TemplateLibrary', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='templates', db_index=True
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    scenario = models.TextField(blank=True, default='')
    instructions = models.TextField(blank=True, default='')

    display_order = models.IntegerField(default=0)
    checklist_json = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'station_templates'
        ordering = ['display_order']

    def __str__(self):
        return f'{self.name} for Exam {self.exam_id}'

    def get_checklist_items(self):
        if not self.checklist_json:
            return []
        if isinstance(self.checklist_json, list):
            return self.checklist_json
        try:
            return json.loads(self.checklist_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_checklist_items(self, items):
        """Store checklist items as JSON. Accepts list or JSON string."""
        if isinstance(items, str):
            self.checklist_json = json.loads(items) if items else []
        else:
            self.checklist_json = items if items else []

    @property
    def total_points(self):
        """Property for easy template access."""
        return self.get_total_points()

    @property
    def item_count(self):
        """Property for easy template access."""
        return self.get_item_count()

    def get_total_points(self):
        items = self.get_checklist_items()
        return sum(float(item.get('points', 0)) for item in items)

    def get_item_count(self):
        return len(self.get_checklist_items())

    def apply_to_path(self, path_id, station_number=None):
        """Apply this template to a path, creating a new Station."""
        from .exam import Station, ChecklistItem
        from .path import Path

        path = Path.objects.get(pk=path_id)

        if station_number is None:
            active_nums = set(
                Station.objects.filter(
                    path_id=path_id, active=True, is_deleted=False
                ).values_list('station_number', flat=True)
            )
            station_number = 1
            while station_number in active_nums:
                station_number += 1

        station = Station(
            path_id=path_id,
            exam_id=path.session.exam_id if path.session else None,
            station_number=station_number,
            name=self.name,
            scenario=self.scenario,
            instructions=self.instructions,
            duration_minutes=path.rotation_minutes or 8,
            active=True,
        )
        station.save()

        items = self.get_checklist_items()
        for item_data in items:
            ChecklistItem.objects.create(
                station=station,
                item_number=item_data.get('item_number', 1),
                description=item_data.get('description', ''),
                points=float(item_data.get('points', 1)),
                rubric_type=item_data.get('scoring_type', 'binary'),
                category=item_data.get('section', ''),
                ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
            )
        return station

    def to_dict(self):
        return {
            'id': self.id,
            'exam_id': str(self.exam_id),
            'name': self.name,
            'description': self.description,
            'scenario': self.scenario,
            'instructions': self.instructions,
            'display_order': self.display_order,
            'item_count': self.get_item_count(),
            'total_points': self.get_total_points(),
            'is_active': self.is_active,
        }
