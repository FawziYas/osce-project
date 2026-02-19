"""
Template Library model – collections of station templates.
"""
from django.db import models
from .mixins import TimestampMixin


class TemplateLibrary(TimestampMixin):
    """A library/collection of station templates."""

    id = models.AutoField(primary_key=True)
    exam = models.ForeignKey(
        'core.Exam', on_delete=models.CASCADE,
        related_name='template_libraries', db_index=True
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=7, default='#0d6efd')
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'template_libraries'
        ordering = ['display_order']

    def __str__(self):
        return self.name

    @property
    def active_templates(self):
        """Get all active templates in this library."""
        return self.templates.filter(is_active=True).order_by('display_order', 'id')

    @property
    def template_count(self):
        """Property for easy template access."""
        return self.get_template_count()

    def get_template_count(self):
        return self.templates.filter(is_active=True).count()

    def get_total_items(self):
        total = 0
        for template in self.templates.filter(is_active=True):
            total += template.get_item_count()
        return total

    def get_total_points(self):
        total = 0.0
        for template in self.templates.filter(is_active=True):
            total += template.get_total_points()
        return total

    def to_dict(self):
        return {
            'id': self.id,
            'exam_id': str(self.exam_id),
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'display_order': self.display_order,
            'template_count': self.get_template_count(),
            'total_items': self.get_total_items(),
            'total_points': self.get_total_points(),
            'is_active': self.is_active,
        }
