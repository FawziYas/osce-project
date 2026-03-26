"""
Management command: verify_audit_integrity

Verifies SHA-256 checksums on all AuditLog records to detect tampering.
Reports tampered, missing-checksum, and valid counts.

Usage:
    python manage.py verify_audit_integrity
    python manage.py verify_audit_integrity --fix   # recompute missing checksums
    python manage.py verify_audit_integrity --batch-size 5000
"""
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify SHA-256 checksums on all audit log records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Recompute and save checksums for records with missing checksums',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=2000,
            help='Number of records to process per batch (default: 2000)',
        )

    def handle(self, *args, **options):
        from core.models.audit import AuditLog, compute_checksum

        fix = options['fix']
        batch_size = options['batch_size']

        total = AuditLog.objects.count()
        self.stdout.write(f'Verifying {total} audit log records...\n')

        valid = 0
        tampered = 0
        missing = 0
        fixed = 0
        tampered_ids = []

        qs = AuditLog.objects.all().order_by('id').iterator(chunk_size=batch_size)

        for obj in qs:
            if not obj.checksum:
                missing += 1
                if fix:
                    obj.checksum = compute_checksum(
                        obj.user_id, obj.action, obj.resource_id,
                        obj.timestamp, obj.old_value, obj.new_value,
                    )
                    AuditLog.objects.filter(pk=obj.pk).update(checksum=obj.checksum)
                    fixed += 1
            elif obj.verify_checksum():
                valid += 1
            else:
                tampered += 1
                tampered_ids.append(obj.pk)
                if fix:
                    # Recompute using stored timestamp (correct value is in DB)
                    obj.checksum = compute_checksum(
                        obj.user_id, obj.action, obj.resource_id,
                        obj.timestamp, obj.old_value, obj.new_value,
                    )
                    AuditLog.objects.filter(pk=obj.pk).update(checksum=obj.checksum)
                    fixed += 1

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'  Valid:    {valid}'))
        self.stdout.write(self.style.WARNING(f'  Missing:  {missing}'))
        if fix:
            self.stdout.write(self.style.SUCCESS(f'  Fixed:    {fixed}'))
        if tampered:
            self.stdout.write(self.style.ERROR(f'  TAMPERED: {tampered}'))
            self.stdout.write(self.style.ERROR(
                f'  Tampered IDs: {tampered_ids[:50]}'
                + (' ...' if len(tampered_ids) > 50 else '')
            ))
        else:
            self.stdout.write(self.style.SUCCESS('  No tampered records found.'))
        self.stdout.write('=' * 60 + '\n')

        if tampered:
            sys.exit(1)
