"""
Management command: init_themes

Populates the Theme table with DEFAULT_THEMES.
"""
from django.core.management.base import BaseCommand
from core.models import Theme, DEFAULT_THEMES


class Command(BaseCommand):
    help = 'Initialize default ILO themes in the database'

    def handle(self, *args, **options):
        created = 0
        for data in DEFAULT_THEMES:
            obj, was_created = Theme.objects.get_or_create(
                code=data['code'],
                defaults=data,
            )
            if was_created:
                created += 1
                self.stdout.write(f'  Created theme: {obj.code}')
            else:
                self.stdout.write(f'  Already exists: {obj.code}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. {created} new theme(s) created, {len(DEFAULT_THEMES) - created} already existed.'
        ))
