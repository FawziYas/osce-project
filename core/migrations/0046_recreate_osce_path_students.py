from django.db import migrations


def recreate_table(apps, schema_editor):
    """Recreate osce_path_students table (SQLite only — legacy data fix).
    On PostgreSQL this table never existed in the clean schema, so no-op."""
    if schema_editor.connection.vendor != 'sqlite':
        return
    schema_editor.execute("""
CREATE TABLE IF NOT EXISTS osce_path_students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NULL,
    updated_at INTEGER NULL,
    checkin_time INTEGER NULL,
    checkout_time INTEGER NULL,
    exam_session_id INTEGER NOT NULL REFERENCES examsessions(id) DEFERRABLE INITIALLY DEFERRED,
    osce_path_id INTEGER NOT NULL REFERENCES osce_exam_paths(id) DEFERRABLE INITIALLY DEFERRED,
    student_id INTEGER NOT NULL REFERENCES examiners(id) DEFERRABLE INITIALLY DEFERRED,
    room_assignment_id INTEGER NOT NULL REFERENCES osce_room_assignments(id) DEFERRABLE INITIALLY DEFERRED
)
""")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS idx_osce_path_student_session ON osce_path_students (exam_session_id, student_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscep_exam_se_idx ON osce_path_students (exam_session_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscep_osce_pa_idx ON osce_path_students (osce_path_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscep_student_idx ON osce_path_students (student_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscep_room_as_idx ON osce_path_students (room_assignment_id)")
    schema_editor.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_osce_path_room_student ON osce_path_students (osce_path_id, room_assignment_id, student_id)")


def drop_table(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        return
    schema_editor.execute("DROP TABLE IF EXISTS osce_path_students")


class Migration(migrations.Migration):
    """Recreate osce_path_students table that was accidentally dropped."""

    dependencies = [
        ('core', '0045_examiner_is_dry_user'),
    ]

    operations = [
        migrations.RunPython(recreate_table, drop_table),
    ]
