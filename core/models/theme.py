"""
Theme model – ILO learning-outcome theme categories.
"""
from django.db import models
from .mixins import TimestampMixin


class Theme(TimestampMixin):
    """ILO Theme / Competency Domain."""

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')

    # UI styling
    color = models.CharField(max_length=7, default='#6c757d')
    icon = models.CharField(max_length=50, default='bi-circle')

    # Organisation
    display_order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = 'themes'
        ordering = ['display_order']

    def __str__(self):
        return f'{self.code}: {self.name}'

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'display_order': self.display_order,
            'active': self.active,
            'ilo_count': self.ilos.filter(active=True).count(),
        }


DEFAULT_THEMES = [
    {
        'code': 'MED_KNOWLEDGE',
        'name': 'Medical Knowledge and Foundational Science',
        'description': 'Understanding core medical concepts, anatomy, physiology, pathology, and evidence-based knowledge',
        'color': '#6f42c1',
        'icon': 'bi-book-half',
        'display_order': 1,
    },
    {
        'code': 'DIAGNOSIS',
        'name': 'Patient Care: Diagnosis',
        'description': 'Complete diagnostic process from history taking and physical examination to formulating final diagnosis',
        'color': '#0d6efd',
        'icon': 'bi-clipboard2-pulse',
        'display_order': 2,
    },
    {
        'code': 'MANAGEMENT',
        'name': 'Patient Care: Management',
        'description': 'Treatment planning, implementation, prevention strategies, and medical/surgical interventions',
        'color': '#198754',
        'icon': 'bi-prescription2',
        'display_order': 3,
    },
    {
        'code': 'SYSTEMS_PRACTICE',
        'name': 'Systems-Based Practice',
        'description': 'Evidence-based medicine, health systems knowledge, quality improvement (limited OSCE relevance)',
        'color': '#fd7e14',
        'icon': 'bi-hospital',
        'display_order': 4,
    },
    {
        'code': 'COMMUNICATION',
        'name': 'Communication and Interpersonal Skills',
        'description': 'Effective patient communication, counseling, documentation, and professional interactions',
        'color': '#20c997',
        'icon': 'bi-chat-heart',
        'display_order': 5,
    },
    {
        'code': 'PROFESSIONALISM',
        'name': 'Ethics, Professionalism, and Patient Safety',
        'description': 'Ethical reasoning, professional behavior, patient safety, and cultural competence',
        'color': '#dc3545',
        'icon': 'bi-award',
        'display_order': 6,
    },
    {
        'code': 'PREVENTION',
        'name': 'Patient Care: Prevention',
        'description': 'Health maintenance, disease prevention strategies, patient counseling on individualized health strategies',
        'color': '#198754',
        'icon': 'bi-shield-check',
        'display_order': 7,
    },
]
