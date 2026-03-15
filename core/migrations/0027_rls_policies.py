"""
PostgreSQL Row-Level Security policies.

Defines helper functions and RLS policies for all core tables.
Automatically skipped on SQLite (development).
"""
import sys
from django.db import migrations


# ── SQL for helper functions ──────────────────────────────────────────

RLS_HELPER_FUNCTIONS_SQL = """
-- Returns the current Django role from session variable
CREATE OR REPLACE FUNCTION app_role()
RETURNS TEXT AS $$
  SELECT COALESCE(current_setting('app.current_role', TRUE), 'ANONYMOUS')
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Returns TRUE if role is Superuser or Admin (global access)
CREATE OR REPLACE FUNCTION is_global_role()
RETURNS BOOLEAN AS $$
  SELECT app_role() IN ('SUPERUSER', 'ADMIN')
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Returns TRUE if role is any coordinator type
CREATE OR REPLACE FUNCTION is_coordinator()
RETURNS BOOLEAN AS $$
  SELECT app_role() IN (
    'COORDINATOR_HEAD',
    'COORDINATOR_ORGANIZER',
    'COORDINATOR_RTA'
  )
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Returns current user's department_id as integer
CREATE OR REPLACE FUNCTION app_department_id()
RETURNS BIGINT AS $$
  SELECT NULLIF(current_setting('app.department_id', TRUE), '')::BIGINT
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Returns the current user's id as integer
CREATE OR REPLACE FUNCTION app_user_id()
RETURNS INTEGER AS $$
  SELECT NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Traces a station up to its department_id through:
-- Station → Path → ExamSession → Exam → Course → Department
CREATE OR REPLACE FUNCTION station_department_id(p_station_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   stations      st
  JOIN   paths         pa ON pa.id = st.path_id
  JOIN   exam_sessions se ON se.id = pa.session_id
  JOIN   exams         ex ON ex.id = se.exam_id
  JOIN   courses       c  ON c.id  = ex.course_id
  WHERE  st.id = p_station_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Returns TRUE if examiner is assigned to station
CREATE OR REPLACE FUNCTION examiner_has_station(p_station_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM examiner_assignments
    WHERE station_id  = p_station_id
    AND   examiner_id = app_user_id()
  )
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Helper: get department_id for an exam via course
CREATE OR REPLACE FUNCTION exam_department_id(p_exam_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   exams   ex
  JOIN   courses c ON c.id = ex.course_id
  WHERE  ex.id = p_exam_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Helper: get department_id for a session via exam → course
CREATE OR REPLACE FUNCTION session_department_id(p_session_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   exam_sessions se
  JOIN   exams         ex ON ex.id = se.exam_id
  JOIN   courses       c  ON c.id  = ex.course_id
  WHERE  se.id = p_session_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Helper: get department_id for a path via session → exam → course
CREATE OR REPLACE FUNCTION path_department_id(p_path_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   paths         pa
  JOIN   exam_sessions se ON se.id = pa.session_id
  JOIN   exams         ex ON ex.id = se.exam_id
  JOIN   courses       c  ON c.id  = ex.course_id
  WHERE  pa.id = p_path_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;
"""

RLS_HELPER_FUNCTIONS_REVERSE = """
DROP FUNCTION IF EXISTS path_department_id(UUID);
DROP FUNCTION IF EXISTS session_department_id(UUID);
DROP FUNCTION IF EXISTS exam_department_id(UUID);
DROP FUNCTION IF EXISTS examiner_has_station(UUID);
DROP FUNCTION IF EXISTS station_department_id(UUID);
DROP FUNCTION IF EXISTS app_user_id();
DROP FUNCTION IF EXISTS app_department_id();
DROP FUNCTION IF EXISTS is_coordinator();
DROP FUNCTION IF EXISTS is_global_role();
DROP FUNCTION IF EXISTS app_role();
"""


# ── Enable RLS on all tables ─────────────────────────────────────────

ENABLE_RLS_SQL = """
ALTER TABLE departments          ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments          FORCE  ROW LEVEL SECURITY;
ALTER TABLE courses              ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses              FORCE  ROW LEVEL SECURITY;
ALTER TABLE exams                ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams                FORCE  ROW LEVEL SECURITY;
ALTER TABLE exam_sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_sessions        FORCE  ROW LEVEL SECURITY;
ALTER TABLE paths                ENABLE ROW LEVEL SECURITY;
ALTER TABLE paths                FORCE  ROW LEVEL SECURITY;
ALTER TABLE stations             ENABLE ROW LEVEL SECURITY;
ALTER TABLE stations             FORCE  ROW LEVEL SECURITY;
ALTER TABLE checklist_items      ENABLE ROW LEVEL SECURITY;
ALTER TABLE checklist_items      FORCE  ROW LEVEL SECURITY;
ALTER TABLE examiner_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE examiner_assignments FORCE  ROW LEVEL SECURITY;
ALTER TABLE station_scores       ENABLE ROW LEVEL SECURITY;
ALTER TABLE station_scores       FORCE  ROW LEVEL SECURITY;
ALTER TABLE item_scores          ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_scores          FORCE  ROW LEVEL SECURITY;
"""

DISABLE_RLS_SQL = """
ALTER TABLE item_scores          DISABLE ROW LEVEL SECURITY;
ALTER TABLE station_scores       DISABLE ROW LEVEL SECURITY;
ALTER TABLE examiner_assignments DISABLE ROW LEVEL SECURITY;
ALTER TABLE checklist_items      DISABLE ROW LEVEL SECURITY;
ALTER TABLE stations             DISABLE ROW LEVEL SECURITY;
ALTER TABLE paths                DISABLE ROW LEVEL SECURITY;
ALTER TABLE exam_sessions        DISABLE ROW LEVEL SECURITY;
ALTER TABLE exams                DISABLE ROW LEVEL SECURITY;
ALTER TABLE courses              DISABLE ROW LEVEL SECURITY;
ALTER TABLE departments          DISABLE ROW LEVEL SECURITY;
"""


# ── RLS Policies ─────────────────────────────────────────────────────

RLS_POLICIES_SQL = """
-- ══════════ DEPARTMENTS ══════════
CREATE POLICY dept_select ON departments FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND id = app_department_id())
);
CREATE POLICY dept_insert ON departments FOR INSERT WITH CHECK (is_global_role());
CREATE POLICY dept_update ON departments FOR UPDATE USING (is_global_role());
CREATE POLICY dept_delete ON departments FOR DELETE USING (is_global_role());

-- ══════════ COURSES ══════════
CREATE POLICY course_select ON courses FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND department_id = app_department_id())
);
CREATE POLICY course_insert ON courses FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND department_id = app_department_id())
);
CREATE POLICY course_update ON courses FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND department_id = app_department_id())
);
CREATE POLICY course_delete ON courses FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND department_id = app_department_id())
);

-- ══════════ EXAMS ══════════
CREATE POLICY exam_select ON exams FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);
CREATE POLICY exam_insert ON exams FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);
CREATE POLICY exam_update ON exams FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);
CREATE POLICY exam_delete ON exams FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);

-- ══════════ EXAM_SESSIONS ══════════
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);
CREATE POLICY session_insert ON exam_sessions FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);
CREATE POLICY session_update ON exam_sessions FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);
CREATE POLICY session_delete ON exam_sessions FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);

-- ══════════ PATHS ══════════
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);
CREATE POLICY path_insert ON paths FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);
CREATE POLICY path_update ON paths FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);
CREATE POLICY path_delete ON paths FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);

-- ══════════ STATIONS ══════════
CREATE POLICY station_select ON stations FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(id))
);
CREATE POLICY station_insert ON stations FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);
CREATE POLICY station_update ON stations FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);
CREATE POLICY station_delete ON stations FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);

-- ══════════ CHECKLIST_ITEMS ══════════
CREATE POLICY checklist_select ON checklist_items FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(station_id))
);
CREATE POLICY checklist_insert ON checklist_items FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
CREATE POLICY checklist_update ON checklist_items FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
CREATE POLICY checklist_delete ON checklist_items FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);

-- ══════════ EXAMINER_ASSIGNMENTS ══════════
CREATE POLICY assign_select ON examiner_assignments FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);
CREATE POLICY assign_insert ON examiner_assignments FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
CREATE POLICY assign_update ON examiner_assignments FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
CREATE POLICY assign_delete ON examiner_assignments FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);

-- ══════════ STATION_SCORES ══════════
CREATE POLICY score_select ON station_scores FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id() AND examiner_has_station(station_id))
);
CREATE POLICY score_insert ON station_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id() AND examiner_has_station(station_id))
);
CREATE POLICY score_update ON station_scores FOR UPDATE USING (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id() AND examiner_has_station(station_id))
);
CREATE POLICY score_delete ON station_scores FOR DELETE USING (is_global_role());

-- ══════════ ITEM_SCORES ══════════
CREATE POLICY item_score_select ON item_scores FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND EXISTS (
    SELECT 1 FROM checklist_items ci
    WHERE ci.id = item_scores.checklist_item_id
    AND station_department_id(ci.station_id) = app_department_id()
  )) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM checklist_items ci
    WHERE ci.id = item_scores.checklist_item_id
    AND examiner_has_station(ci.station_id)
  ) AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
    AND ss.examiner_id = app_user_id()
  ))
);
CREATE POLICY item_score_insert ON item_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
    AND ss.examiner_id = app_user_id()
  ) AND EXISTS (
    SELECT 1 FROM checklist_items ci
    WHERE ci.id = item_scores.checklist_item_id
    AND examiner_has_station(ci.station_id)
  ))
);
CREATE POLICY item_score_update ON item_scores FOR UPDATE USING (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
    AND ss.examiner_id = app_user_id()
  ))
);
CREATE POLICY item_score_delete ON item_scores FOR DELETE USING (is_global_role());
"""

RLS_POLICIES_REVERSE = """
-- Drop all policies
DROP POLICY IF EXISTS dept_select ON departments;
DROP POLICY IF EXISTS dept_insert ON departments;
DROP POLICY IF EXISTS dept_update ON departments;
DROP POLICY IF EXISTS dept_delete ON departments;

DROP POLICY IF EXISTS course_select ON courses;
DROP POLICY IF EXISTS course_insert ON courses;
DROP POLICY IF EXISTS course_update ON courses;
DROP POLICY IF EXISTS course_delete ON courses;

DROP POLICY IF EXISTS exam_select ON exams;
DROP POLICY IF EXISTS exam_insert ON exams;
DROP POLICY IF EXISTS exam_update ON exams;
DROP POLICY IF EXISTS exam_delete ON exams;

DROP POLICY IF EXISTS session_select ON exam_sessions;
DROP POLICY IF EXISTS session_insert ON exam_sessions;
DROP POLICY IF EXISTS session_update ON exam_sessions;
DROP POLICY IF EXISTS session_delete ON exam_sessions;

DROP POLICY IF EXISTS path_select ON paths;
DROP POLICY IF EXISTS path_insert ON paths;
DROP POLICY IF EXISTS path_update ON paths;
DROP POLICY IF EXISTS path_delete ON paths;

DROP POLICY IF EXISTS station_select ON stations;
DROP POLICY IF EXISTS station_insert ON stations;
DROP POLICY IF EXISTS station_update ON stations;
DROP POLICY IF EXISTS station_delete ON stations;

DROP POLICY IF EXISTS checklist_select ON checklist_items;
DROP POLICY IF EXISTS checklist_insert ON checklist_items;
DROP POLICY IF EXISTS checklist_update ON checklist_items;
DROP POLICY IF EXISTS checklist_delete ON checklist_items;

DROP POLICY IF EXISTS assign_select ON examiner_assignments;
DROP POLICY IF EXISTS assign_insert ON examiner_assignments;
DROP POLICY IF EXISTS assign_update ON examiner_assignments;
DROP POLICY IF EXISTS assign_delete ON examiner_assignments;

DROP POLICY IF EXISTS score_select ON station_scores;
DROP POLICY IF EXISTS score_insert ON station_scores;
DROP POLICY IF EXISTS score_update ON station_scores;
DROP POLICY IF EXISTS score_delete ON station_scores;

DROP POLICY IF EXISTS item_score_select ON item_scores;
DROP POLICY IF EXISTS item_score_insert ON item_scores;
DROP POLICY IF EXISTS item_score_update ON item_scores;
DROP POLICY IF EXISTS item_score_delete ON item_scores;
"""


class Migration(migrations.Migration):
    """
    PostgreSQL Row-Level Security: helper functions + enable RLS + policies.
    Automatically skipped on SQLite.
    """

    dependencies = [
        ('core', '0026_backfill_course_departments'),
    ]

    operations = [
        migrations.RunSQL(
            sql=RLS_HELPER_FUNCTIONS_SQL,
            reverse_sql=RLS_HELPER_FUNCTIONS_REVERSE,
        ),
        migrations.RunSQL(
            sql=ENABLE_RLS_SQL,
            reverse_sql=DISABLE_RLS_SQL,
        ),
        migrations.RunSQL(
            sql=RLS_POLICIES_SQL,
            reverse_sql=RLS_POLICIES_REVERSE,
        ),
    ]

    def apply(self, project_state, schema_editor, collect_sql=False):
        """Skip on non-PostgreSQL databases."""
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            sys.stdout.write(
                f"\n  [RLS] Skipping — database engine is not PostgreSQL."
                f"\n  [RLS] Current engine: {db_engine}"
                f"\n  [RLS] RLS policies will activate when you migrate to PostgreSQL.\n"
            )
            # Still record the migration as applied
            return project_state
        return super().apply(project_state, schema_editor, collect_sql)

    def unapply(self, project_state, schema_editor, collect_sql=False):
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            return project_state
        return super().unapply(project_state, schema_editor, collect_sql)
