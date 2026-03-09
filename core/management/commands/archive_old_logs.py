"""
Management command: archive_old_logs

Moves AuditLog records older than N days to the AuditLogArchive table.
Never deletes — only archives.

Usage:
    python manage.py archive_old_logs --days=365
    python manage.py archive_old_logs --days=90 --batch-size=5000 --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Archive audit logs older than N days to the AuditLogArchive table.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Archive logs older than this many days (default: 365)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of rows to process per batch (default: 1000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many rows would be archived without doing it',
        )

    def handle(self, *args, **options):
        from core.models.audit import AuditLog, AuditLogArchive

        days = options['days']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(days=days)

        qs = AuditLog.objects.filter(timestamp__lt=cutoff)
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f'No audit logs older than {days} days to archive.'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would archive {total} audit log(s) older than {cutoff.date()}.'
            ))
            return

        self.stdout.write(f'Archiving {total} audit log(s) older than {cutoff.date()}...')

        archived = 0
        while True:
            batch = list(qs.order_by('id')[:batch_size].values(
                'id', 'timestamp', 'user_id', 'username', 'user_role',
                'department_id', 'action', 'status',
                'resource_type', 'resource_id', 'resource_label',
                'old_value', 'new_value', 'description',
                'ip_address', 'user_agent', 'request_method', 'request_path',
                'extra_data',
            ))

            if not batch:
                break

            # Bulk-create archive rows
            archive_objs = [
                AuditLogArchive(**row) for row in batch
            ]
            AuditLogArchive.objects.bulk_create(archive_objs, ignore_conflicts=True)

            # Delete the originals
            batch_ids = [row['id'] for row in batch]
            AuditLog.objects.filter(id__in=batch_ids).delete()

            archived += len(batch)
            self.stdout.write(f'  Archived {archived}/{total}...')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Archived {archived} audit log(s) to AuditLogArchive.'
        ))
