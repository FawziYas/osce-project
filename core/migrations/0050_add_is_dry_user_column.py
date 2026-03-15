"""
Migration 0045 used SeparateDatabaseAndState with empty database_operations,
assuming the column was manually pre-created in the SQLite dev database.
On a fresh PostgreSQL database the column was never created.
This migration adds it now, idempotently.
"""
from django.db import migrations


def add_is_dry_user(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            'ALTER TABLE examiners ADD COLUMN IF NOT EXISTS is_dry_user BOOLEAN NOT NULL DEFAULT FALSE'
        )
    # SQLite: column already exists from the original manual add; no-op.


def remove_is_dry_user(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            'ALTER TABLE examiners DROP COLUMN IF EXISTS is_dry_user'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_add_can_open_dry_grading_permission'),
    ]

    operations = [
        migrations.RunPython(add_is_dry_user, remove_is_dry_user),
    ]
