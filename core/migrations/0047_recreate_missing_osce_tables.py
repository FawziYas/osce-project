from django.db import migrations


def recreate_tables(apps, schema_editor):
    """Recreate legacy tables dropped from the SQLite dev DB.
    These tables are not in the current models; no-op on PostgreSQL."""
    if schema_editor.connection.vendor != 'sqlite':
        return

    schema_editor.execute("""
CREATE TABLE IF NOT EXISTS osce_exam_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NULL,
    updated_at INTEGER NULL,
    exam_session_id CHAR(32) NOT NULL REFERENCES examsessions(id) DEFERRABLE INITIALLY DEFERRED,
    path_number INTEGER NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 8,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at INTEGER NULL,
    completed_at INTEGER NULL
)
""")
    schema_editor.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_session_osce_path_number ON osce_exam_paths (exam_session_id, path_number)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS idx_osce_path_session_status ON osce_exam_paths (exam_session_id, status)")

    schema_editor.execute("""
CREATE TABLE IF NOT EXISTS osce_room_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NULL,
    updated_at INTEGER NULL,
    osce_path_id INTEGER NOT NULL REFERENCES osce_exam_paths(id) DEFERRABLE INITIALLY DEFERRED,
    exam_session_id CHAR(32) NOT NULL REFERENCES examsessions(id) DEFERRABLE INITIALLY DEFERRED,
    room_number INTEGER NOT NULL,
    room_name VARCHAR(100) NOT NULL DEFAULT '',
    station_id CHAR(32) NOT NULL REFERENCES stations(id) DEFERRABLE INITIALLY DEFERRED,
    examiner_id INTEGER NULL REFERENCES examiners(id) DEFERRABLE INITIALLY DEFERRED,
    examiner_name VARCHAR(200) NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
)
""")
    schema_editor.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_osce_path_room_number ON osce_room_assignments (osce_path_id, room_number)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS idx_osce_room_session_station ON osce_room_assignments (exam_session_id, station_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscero_osce_pa_idx ON osce_room_assignments (osce_path_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscero_station_idx ON osce_room_assignments (station_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscero_examine_idx ON osce_room_assignments (examiner_id)")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_oscero_exam_se_idx ON osce_room_assignments (exam_session_id)")

    schema_editor.execute("""
CREATE TABLE IF NOT EXISTS path_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NULL,
    updated_at INTEGER NULL,
    student_path_id INTEGER NULL,
    path_id CHAR(32) NULL REFERENCES paths(id) DEFERRABLE INITIALLY DEFERRED,
    station_id CHAR(32) NOT NULL REFERENCES stations(id) DEFERRABLE INITIALLY DEFERRED,
    sequence_order INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
)
""")
    schema_editor.execute("CREATE INDEX IF NOT EXISTS core_pathst_station_idx ON path_stations (station_id)")


def drop_tables(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        return
    schema_editor.execute("DROP TABLE IF EXISTS path_stations")
    schema_editor.execute("DROP TABLE IF EXISTS osce_room_assignments")
    schema_editor.execute("DROP TABLE IF EXISTS osce_exam_paths")


class Migration(migrations.Migration):
    """Recreate osce_exam_paths, osce_room_assignments, and path_stations tables
    that were accidentally dropped from the database."""

    dependencies = [
        ('core', '0046_recreate_osce_path_students'),
    ]

    operations = [
        migrations.RunPython(recreate_tables, drop_tables),
    ]
