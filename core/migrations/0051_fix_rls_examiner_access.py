"""
Fix RLS SELECT policies: allow examiners to read exam_sessions, paths,
exams, courses, and departments that relate to their assignments.

Without this, examiner views that JOIN to these tables return zero rows
because RLS blocks the read.
"""
import sys
from django.db import migrations


FIX_SQL = """
-- ── departments: examiner can see own department ────────────────
DROP POLICY IF EXISTS department_select ON departments;
CREATE POLICY department_select ON departments FOR SELECT USING (
  is_global_role() OR
  id = app_department_id()
);

-- ── courses: add examiner clause ────────────────────────────────
DROP POLICY IF EXISTS course_select ON courses;
CREATE POLICY course_select ON courses FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND department_id = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM exams e
    JOIN exam_sessions es ON es.exam_id = e.id
    JOIN examiner_assignments ea ON ea.session_id = es.id
    WHERE e.course_id = courses.id
      AND ea.examiner_id = app_user_id()
  ))
);

-- ── exams: add examiner clause ──────────────────────────────────
DROP POLICY IF EXISTS exam_select ON exams;
CREATE POLICY exam_select ON exams FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM exam_sessions es
    JOIN examiner_assignments ea ON ea.session_id = es.id
    WHERE es.exam_id = exams.id
      AND ea.examiner_id = app_user_id()
  ))
);

-- ── exam_sessions: add examiner clause ──────────────────────────
DROP POLICY IF EXISTS session_select ON exam_sessions;
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM examiner_assignments ea
    WHERE ea.session_id = exam_sessions.id
      AND ea.examiner_id = app_user_id()
  ))
);

-- ── paths: add examiner clause ──────────────────────────────────
DROP POLICY IF EXISTS path_select ON paths;
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM stations st
    JOIN examiner_assignments ea ON ea.station_id = st.id
    WHERE st.path_id = paths.id
      AND ea.examiner_id = app_user_id()
  ))
);
"""

REVERSE_SQL = """
-- Revert to original policies without examiner clauses
DROP POLICY IF EXISTS department_select ON departments;
CREATE POLICY department_select ON departments FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND id = app_department_id())
);

DROP POLICY IF EXISTS course_select ON courses;
CREATE POLICY course_select ON courses FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND department_id = app_department_id())
);

DROP POLICY IF EXISTS exam_select ON exams;
CREATE POLICY exam_select ON exams FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);

DROP POLICY IF EXISTS session_select ON exam_sessions;
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);

DROP POLICY IF EXISTS path_select ON paths;
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_add_is_dry_user_column'),
    ]

    operations = [
        migrations.RunSQL(sql=FIX_SQL, reverse_sql=REVERSE_SQL),
    ]

    def apply(self, project_state, schema_editor, collect_sql=False):
        """Skip on non-PostgreSQL databases."""
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            sys.stdout.write(
                "\n  [RLS] Skipping 0051 — not PostgreSQL.\n"
            )
            return project_state
        return super().apply(project_state, schema_editor, collect_sql)

    def unapply(self, project_state, schema_editor, collect_sql=False):
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            return project_state
        return super().unapply(project_state, schema_editor, collect_sql)
