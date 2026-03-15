# Manual migration to add department column that should have been in 0001_initial

from django.db import migrations, models


def add_department_column(apps, schema_editor):
    """Add department column; idempotent (ignores duplicate-column errors)."""
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute(
            "ALTER TABLE examiners ADD COLUMN IF NOT EXISTS department VARCHAR(100) DEFAULT '' NOT NULL"
        )
    else:
        # SQLite: use PRAGMA to bypass FK constraint check
        schema_editor.execute('PRAGMA foreign_keys=OFF')
        try:
            schema_editor.execute(
                'ALTER TABLE examiners ADD COLUMN department VARCHAR(100) DEFAULT "" NOT NULL'
            )
        except Exception:
            pass  # Column might already exist
        finally:
            schema_editor.execute('PRAGMA foreign_keys=ON')


def reverse_add_department(apps, schema_editor):
    """Reverse: drop the column."""
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        try:
            schema_editor.execute('ALTER TABLE examiners DROP COLUMN IF EXISTS department')
        except Exception:
            pass
    else:
        schema_editor.execute('PRAGMA foreign_keys=OFF')
        try:
            schema_editor.execute('ALTER TABLE examiners DROP COLUMN department')
        except Exception:
            pass
        finally:
            schema_editor.execute('PRAGMA foreign_keys=ON')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_set_default_short_code'),
    ]

    operations = [
        migrations.RunPython(add_department_column, reverse_add_department),
    ]
