"""
Management command: clear_login_audit_logs

Deletes LoginAuditLog records in batches. This command is deliberate and
requires --confirm to actually perform deletions. Use --dry-run to preview
how many rows would be removed.

Usage:
    python manage.py clear_login_audit_logs --dry-run
    python manage.py clear_login_audit_logs --confirm
    python manage.py clear_login_audit_logs --older-than-days=90 --confirm
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Delete LoginAuditLog entries. Requires --confirm to perform deletion.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of rows to delete per batch (default: 1000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many rows would be deleted without doing it',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Perform the deletion (required to actually delete rows)',
        )
        parser.add_argument(
            '--older-than-days',
            type=int,
            default=None,
            help='Only delete entries older than this many days',
        )

    def handle(self, *args, **options):
        from core.models.login_audit import LoginAuditLog

        batch_size = options['batch_size']
        dry_run = options['dry_run']
        confirm = options['confirm']
        older_than = options['older_than_days']

        qs = LoginAuditLog.objects.all()

        if older_than is not None:
            cutoff = timezone.now() - timedelta(days=older_than)
            qs = qs.filter(timestamp__lt=cutoff)

        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No login audit logs match the query.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would delete {total} LoginAuditLog row(s).'
            ))
            return

        if not confirm:
            self.stdout.write(self.style.ERROR(
                f'Aborting: {total} LoginAuditLog row(s) would be deleted. Re-run with --confirm to proceed.'
            ))
            return

        self.stdout.write(f'Deleting {total} LoginAuditLog row(s) in batches of {batch_size}...')

        deleted = 0
        while True:
            batch_ids = list(qs.order_by('id').values_list('id', flat=True)[:batch_size])
            if not batch_ids:
                break
            LoginAuditLog.objects.filter(id__in=batch_ids).delete()
            deleted += len(batch_ids)
            self.stdout.write(f'  Deleted {deleted}/{total}...')

        self.stdout.write(self.style.SUCCESS(f'Done. Deleted {deleted} LoginAuditLog row(s).'))
