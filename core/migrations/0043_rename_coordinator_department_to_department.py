"""
Consolidate Examiner department fields:
- Remove the `department` CharField (VARCHAR)
- Rename `coordinator_department` FK to `department`
- Update constraints to use new field name
"""
from django.db import migrations, models


def forwards(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        # 1. Drop the VARCHAR department column (added by migration 0042)
        cursor.execute('ALTER TABLE examiners DROP COLUMN department')
        # 2. Rename coordinator_department_id to department_id
        cursor.execute(
            'ALTER TABLE examiners RENAME COLUMN coordinator_department_id TO department_id'
        )


def backwards(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        # Reverse: rename back and re-add the VARCHAR column
        cursor.execute(
            'ALTER TABLE examiners RENAME COLUMN department_id TO coordinator_department_id'
        )
        cursor.execute(
            'ALTER TABLE examiners ADD COLUMN department VARCHAR(100) NOT NULL DEFAULT ""'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_add_missing_department_to_examiner'),
    ]

    operations = [
        # Step 1: Apply DB-level changes (column drop + rename)
        migrations.RunPython(forwards, backwards),

        # Step 2: Update Django's internal model state to match the DB
        # (no SQL is executed — only the migration state machine is updated)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # Remove old constraints from state
                migrations.RemoveConstraint(
                    model_name='examiner',
                    name='coordinator_must_have_department',
                ),
                migrations.RemoveConstraint(
                    model_name='examiner',
                    name='non_coordinator_no_dept_fields',
                ),
                # Remove the CharField from state
                migrations.RemoveField(
                    model_name='examiner',
                    name='department',
                ),
                # Rename the FK from coordinator_department → department
                migrations.RenameField(
                    model_name='examiner',
                    old_name='coordinator_department',
                    new_name='department',
                ),
                # Add updated constraints to state
                migrations.AddConstraint(
                    model_name='examiner',
                    constraint=models.CheckConstraint(
                        condition=models.Q(
                            models.Q(role='coordinator', _negated=True)
                        ) | models.Q(department__isnull=False),
                        name='coordinator_must_have_department',
                    ),
                ),
                migrations.AddConstraint(
                    model_name='examiner',
                    constraint=models.CheckConstraint(
                        condition=models.Q(role='coordinator') | models.Q(
                            coordinator_position='',
                        ),
                        name='non_coordinator_no_position',
                    ),
                ),
            ],
        ),
    ]
