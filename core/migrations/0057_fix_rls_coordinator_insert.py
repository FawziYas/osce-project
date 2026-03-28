"""
Fix RLS INSERT policies for coordinator users.

The original INSERT WITH CHECK policies for exams, exam_sessions, and paths
use lookup functions (exam_department_id, session_department_id,
path_department_id) that query the table being inserted into.  During an
INSERT the new row is not yet visible to those helper functions, so the
check always returns NULL → the INSERT is denied for coordinators.

Fix: rewrite INSERT checks to reference columns of the NEW row directly
and join only to *other* tables that already contain the data.
"""
import sys
from django.db import migrations


FIX_SQL = """
-- ══════════ EXAMS — fix INSERT ══════════
-- Instead of exam_department_id(id) which queries the exams table
-- (row not yet visible), join directly from the new row's course_id.
DROP POLICY IF EXISTS exam_insert ON exams;
CREATE POLICY exam_insert ON exams FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM courses c WHERE c.id = course_id
  ) = app_department_id())
);

-- ══════════ EXAM_SESSIONS — fix INSERT ══════════
-- Instead of session_department_id(id) which queries exam_sessions
-- (row not yet visible), look up department via the new row's exam_id.
DROP POLICY IF EXISTS session_insert ON exam_sessions;
CREATE POLICY session_insert ON exam_sessions FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(exam_id) = app_department_id())
);

-- ══════════ PATHS — fix INSERT ══════════
-- Instead of path_department_id(id) which queries paths (row not yet
-- visible), look up department via the new row's session_id.
DROP POLICY IF EXISTS path_insert ON paths;
CREATE POLICY path_insert ON paths FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND session_department_id(session_id) = app_department_id())
);

-- ══════════ STATIONS — fix INSERT ══════════
-- Instead of station_department_id(id) which queries stations (row not
-- yet visible), look up department via the new row's path_id.
DROP POLICY IF EXISTS station_insert ON stations;
CREATE POLICY station_insert ON stations FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND path_department_id(path_id) = app_department_id())
);

-- ══════════ CHECKLIST_ITEMS — fix INSERT ══════════
-- station_department_id(station_id) is fine here because it queries the
-- *stations* table (not checklist_items), so the lookup works.  But let's
-- be consistent and explicit.
DROP POLICY IF EXISTS checklist_insert ON checklist_items;
CREATE POLICY checklist_insert ON checklist_items FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);

-- ══════════ EXAMINER_ASSIGNMENTS — fix INSERT ══════════
-- station_department_id(station_id) queries stations, not
-- examiner_assignments, so this already works — but re-create for clarity.
DROP POLICY IF EXISTS assign_insert ON examiner_assignments;
CREATE POLICY assign_insert ON examiner_assignments FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
"""

REVERSE_SQL = """
-- Revert to original policies from 0027
DROP POLICY IF EXISTS exam_insert ON exams;
CREATE POLICY exam_insert ON exams FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);

DROP POLICY IF EXISTS session_insert ON exam_sessions;
CREATE POLICY session_insert ON exam_sessions FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);

DROP POLICY IF EXISTS path_insert ON paths;
CREATE POLICY path_insert ON paths FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);

DROP POLICY IF EXISTS station_insert ON stations;
CREATE POLICY station_insert ON stations FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);

DROP POLICY IF EXISTS checklist_insert ON checklist_items;
CREATE POLICY checklist_insert ON checklist_items FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);

DROP POLICY IF EXISTS assign_insert ON examiner_assignments;
CREATE POLICY assign_insert ON examiner_assignments FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0056_audit_checksum_immutability'),
    ]

    operations = [
        migrations.RunSQL(sql=FIX_SQL, reverse_sql=REVERSE_SQL),
    ]

    def apply(self, project_state, schema_editor, collect_sql=False):
        """Skip on non-PostgreSQL databases."""
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            sys.stdout.write(
                "\n  [RLS] Skipping 0057 — not PostgreSQL.\n"
            )
            return project_state
        return super().apply(project_state, schema_editor, collect_sql)

    def unapply(self, project_state, schema_editor, collect_sql=False):
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            return project_state
        return super().unapply(project_state, schema_editor, collect_sql)
