"""
Department model – used to assign coordinators to organisational units.
"""
from django.db import models
from .mixins import TimestampMixin


class Department(TimestampMixin):
    """
    An organisational department (e.g. Medicine, Surgery, Paediatrics).
    Coordinators are linked to a department and assigned a position (Head / RTA).
    """
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        db_table = 'departments'
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return self.name

    @property
    def head_coordinator(self):
        """Return the coordinator with position=head for this dept, if any."""
        return self.members.filter(
            coordinator_position='head', is_deleted=False
        ).first()

    @property
    def rta_coordinators(self):
        """Return all RTA coordinators for this dept."""
        return self.members.filter(
            coordinator_position='rta', is_deleted=False
        )
