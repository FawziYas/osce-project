from django.db import migrations


class Migration(migrations.Migration):
    """Drop unused OSCE tables and legacy PathStation table.

    These models (OSCEExamPath, OSCERoomAssignment, OSCEPathStudent, PathStation)
    are not used anywhere in the application — they are remnants of an older
    design that was replaced by the Path/Station/SessionStudent architecture.
    """

    dependencies = [
        ('core', '0047_recreate_missing_osce_tables'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Drop tables in correct order (FK dependencies)
                migrations.RunSQL(
                    sql=(
                        "DROP TABLE IF EXISTS osce_path_students;"
                        "DROP TABLE IF EXISTS osce_room_assignments;"
                        "DROP TABLE IF EXISTS osce_exam_paths;"
                        "DROP TABLE IF EXISTS path_stations;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.DeleteModel(name='OSCEPathStudent'),
                migrations.DeleteModel(name='OSCERoomAssignment'),
                migrations.DeleteModel(name='OSCEExamPath'),
                migrations.DeleteModel(name='PathStation'),
            ],
        ),
    ]
