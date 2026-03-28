"""
Fix RLS cross-table infinite recursion on ALL tables.

Migration 0058 fixed self-referencing helper functions but KEPT
examiner clauses that create cross-table recursion:

  exam_select  →  queries exam_sessions  →  session_select
               →  queries exams  →  exam_select  →  LOOP!

  station_select  →  examiner_has_station()  →  queries
  examiner_assignments  →  assign_select  →  queries stations
               →  station_select  →  LOOP!

Fix: remove ALL examiner cross-table subqueries from RLS policies.
Every policy now uses ONLY:
  1) is_global_role()  — admin/superuser bypass
  2) Inline department check via parent tables ONLY (always goes
     UP the hierarchy, never sideways/down — terminates at courses
     which has a direct department_id column)
  3) For examiner_assignments / station_scores: simple column
     comparison  examiner_id = app_user_id()  (self-contained)

Examiner visibility into exams/sessions/paths/stations is handled
at the Django view level, not RLS.
"""
import sys
from django.db import migrations


FIX_SQL = """
-- ════════════════════════════════════════════════════════════════
-- DEPARTMENTS — unchanged (already safe, no subqueries)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS department_select ON departments;
CREATE POLICY department_select ON departments FOR SELECT USING (
  is_global_role() OR id = app_department_id()
);
-- INSERT/UPDATE/DELETE unchanged (is_global_role() only)


-- ════════════════════════════════════════════════════════════════
-- COURSES — remove examiner cross-table clause from 0051
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS course_select ON courses;
CREATE POLICY course_select ON courses FOR SELECT USING (
  is_global_role() OR
  department_id = app_department_id()
);
-- INSERT/UPDATE/DELETE unchanged (coordinator + department_id check)


-- ════════════════════════════════════════════════════════════════
-- EXAMS — SELECT: remove examiner clause, keep dept-only check
-- Subquery: courses only (1 level UP, terminates at direct column)
-- INSERT/UPDATE/DELETE: coordinator dept check only (safe)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS exam_select ON exams;
CREATE POLICY exam_select ON exams FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id FROM courses c WHERE c.id = exams.course_id)
    = app_department_id()
);

DROP POLICY IF EXISTS exam_insert ON exams;
CREATE POLICY exam_insert ON exams FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM courses c WHERE c.id = course_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS exam_update ON exams;
CREATE POLICY exam_update ON exams FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM courses c WHERE c.id = exams.course_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS exam_delete ON exams;
CREATE POLICY exam_delete ON exams FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM courses c WHERE c.id = exams.course_id
  ) = app_department_id())
);


-- ════════════════════════════════════════════════════════════════
-- EXAM_SESSIONS — dept check via exams→courses (2 levels UP)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS session_select ON exam_sessions;
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM exams e JOIN courses c ON c.id = e.course_id
   WHERE e.id = exam_sessions.exam_id
  ) = app_department_id()
);

DROP POLICY IF EXISTS session_insert ON exam_sessions;
CREATE POLICY session_insert ON exam_sessions FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exams e JOIN courses c ON c.id = e.course_id
    WHERE e.id = exam_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS session_update ON exam_sessions;
CREATE POLICY session_update ON exam_sessions FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exams e JOIN courses c ON c.id = e.course_id
    WHERE e.id = exam_sessions.exam_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS session_delete ON exam_sessions;
CREATE POLICY session_delete ON exam_sessions FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exams e JOIN courses c ON c.id = e.course_id
    WHERE e.id = exam_sessions.exam_id
  ) = app_department_id())
);


-- ════════════════════════════════════════════════════════════════
-- PATHS — dept check via sessions→exams→courses (3 levels UP)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS path_select ON paths;
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM exam_sessions es
   JOIN exams e ON e.id = es.exam_id
   JOIN courses c ON c.id = e.course_id
   WHERE es.id = paths.session_id
  ) = app_department_id()
);

DROP POLICY IF EXISTS path_insert ON paths;
CREATE POLICY path_insert ON paths FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exam_sessions es
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE es.id = session_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS path_update ON paths;
CREATE POLICY path_update ON paths FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exam_sessions es
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE es.id = paths.session_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS path_delete ON paths;
CREATE POLICY path_delete ON paths FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exam_sessions es
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE es.id = paths.session_id
  ) = app_department_id())
);


-- ════════════════════════════════════════════════════════════════
-- STATIONS — dept check via paths→sessions→exams→courses (4 UP)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS station_select ON stations;
CREATE POLICY station_select ON stations FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM paths p
   JOIN exam_sessions es ON es.id = p.session_id
   JOIN exams e ON e.id = es.exam_id
   JOIN courses c ON c.id = e.course_id
   WHERE p.id = stations.path_id
  ) = app_department_id()
);

DROP POLICY IF EXISTS station_insert ON stations;
CREATE POLICY station_insert ON stations FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM paths p
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE p.id = path_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS station_update ON stations;
CREATE POLICY station_update ON stations FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM paths p
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE p.id = stations.path_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS station_delete ON stations;
CREATE POLICY station_delete ON stations FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM paths p
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE p.id = stations.path_id
  ) = app_department_id())
);


-- ════════════════════════════════════════════════════════════════
-- CHECKLIST_ITEMS — dept check via stations→…→courses (5 UP)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS checklist_select ON checklist_items;
CREATE POLICY checklist_select ON checklist_items FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM stations st
   JOIN paths p ON p.id = st.path_id
   JOIN exam_sessions es ON es.id = p.session_id
   JOIN exams e ON e.id = es.exam_id
   JOIN courses c ON c.id = e.course_id
   WHERE st.id = checklist_items.station_id
  ) = app_department_id()
);

DROP POLICY IF EXISTS checklist_insert ON checklist_items;
CREATE POLICY checklist_insert ON checklist_items FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = station_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS checklist_update ON checklist_items;
CREATE POLICY checklist_update ON checklist_items FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = checklist_items.station_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS checklist_delete ON checklist_items;
CREATE POLICY checklist_delete ON checklist_items FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = checklist_items.station_id
  ) = app_department_id())
);


-- ════════════════════════════════════════════════════════════════
-- EXAMINER_ASSIGNMENTS — dept check + self-contained examiner_id
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS assign_select ON examiner_assignments;
CREATE POLICY assign_select ON examiner_assignments FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM stations st
   JOIN paths p ON p.id = st.path_id
   JOIN exam_sessions es ON es.id = p.session_id
   JOIN exams e ON e.id = es.exam_id
   JOIN courses c ON c.id = e.course_id
   WHERE st.id = examiner_assignments.station_id
  ) = app_department_id() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);

DROP POLICY IF EXISTS assign_insert ON examiner_assignments;
CREATE POLICY assign_insert ON examiner_assignments FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = station_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS assign_update ON examiner_assignments;
CREATE POLICY assign_update ON examiner_assignments FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = examiner_assignments.station_id
  ) = app_department_id())
);

DROP POLICY IF EXISTS assign_delete ON examiner_assignments;
CREATE POLICY assign_delete ON examiner_assignments FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = examiner_assignments.station_id
  ) = app_department_id())
);


-- ════════════════════════════════════════════════════════════════
-- STATION_SCORES — dept check + self-contained examiner_id
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS score_select ON station_scores;
CREATE POLICY score_select ON station_scores FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM stations st
   JOIN paths p ON p.id = st.path_id
   JOIN exam_sessions es ON es.id = p.session_id
   JOIN exams e ON e.id = es.exam_id
   JOIN courses c ON c.id = e.course_id
   WHERE st.id = station_scores.station_id
  ) = app_department_id() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);

DROP POLICY IF EXISTS score_insert ON station_scores;
CREATE POLICY score_insert ON station_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);

DROP POLICY IF EXISTS score_update ON station_scores;
CREATE POLICY score_update ON station_scores FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = station_scores.station_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);

DROP POLICY IF EXISTS score_delete ON station_scores;
CREATE POLICY score_delete ON station_scores FOR DELETE USING (is_global_role());


-- ════════════════════════════════════════════════════════════════
-- ITEM_SCORES — dept check + self-contained examiner check
-- The examiner check queries station_scores which is safe
-- (score_select has examiner_id = app_user_id(), no cross-table)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS item_score_select ON item_scores;
CREATE POLICY item_score_select ON item_scores FOR SELECT USING (
  is_global_role() OR
  (SELECT c.department_id
   FROM checklist_items ci
   JOIN stations st ON st.id = ci.station_id
   JOIN paths p ON p.id = st.path_id
   JOIN exam_sessions es ON es.id = p.session_id
   JOIN exams e ON e.id = es.exam_id
   JOIN courses c ON c.id = e.course_id
   WHERE ci.id = item_scores.checklist_item_id
  ) = app_department_id() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
      AND ss.examiner_id = app_user_id()
  ))
);

DROP POLICY IF EXISTS item_score_insert ON item_scores;
CREATE POLICY item_score_insert ON item_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = station_score_id
      AND ss.examiner_id = app_user_id()
  ))
);

DROP POLICY IF EXISTS item_score_update ON item_scores;
CREATE POLICY item_score_update ON item_scores FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM checklist_items ci
    JOIN stations st ON st.id = ci.station_id
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE ci.id = item_scores.checklist_item_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
      AND ss.examiner_id = app_user_id()
  ))
);

DROP POLICY IF EXISTS item_score_delete ON item_scores;
CREATE POLICY item_score_delete ON item_scores FOR DELETE USING (is_global_role());
"""


REVERSE_SQL = """
-- Revert to 0058 state (has cross-table recursion but is the known state)
-- This is a safety net; the forward migration is the intended fix.

-- courses (restore 0051 examiner clause)
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

-- exams (restore 0058)
DROP POLICY IF EXISTS exam_select ON exams;
CREATE POLICY exam_select ON exams FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM courses c WHERE c.id = exams.course_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM exam_sessions es
    JOIN examiner_assignments ea ON ea.session_id = es.id
    WHERE es.exam_id = exams.id
      AND ea.examiner_id = app_user_id()
  ))
);

-- exam_sessions (restore 0058)
DROP POLICY IF EXISTS session_select ON exam_sessions;
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM exams e JOIN courses c ON c.id = e.course_id
    WHERE e.id = exam_sessions.exam_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM examiner_assignments ea
    WHERE ea.session_id = exam_sessions.id
      AND ea.examiner_id = app_user_id()
  ))
);

-- paths (restore 0058)
DROP POLICY IF EXISTS path_select ON paths;
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM exam_sessions es
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE es.id = paths.session_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM stations st
    JOIN examiner_assignments ea ON ea.station_id = st.id
    WHERE st.path_id = paths.id
      AND ea.examiner_id = app_user_id()
  ))
);

-- stations (restore 0058)
DROP POLICY IF EXISTS station_select ON stations;
CREATE POLICY station_select ON stations FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM paths p
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE p.id = stations.path_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(id))
);

-- checklist_items (restore 0058)
DROP POLICY IF EXISTS checklist_select ON checklist_items;
CREATE POLICY checklist_select ON checklist_items FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = checklist_items.station_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(station_id))
);

-- examiner_assignments (restore 0058)
DROP POLICY IF EXISTS assign_select ON examiner_assignments;
CREATE POLICY assign_select ON examiner_assignments FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = examiner_assignments.station_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);

-- station_scores (restore 0058)
DROP POLICY IF EXISTS score_select ON station_scores;
CREATE POLICY score_select ON station_scores FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = station_scores.station_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id()
   AND examiner_has_station(station_id))
);
DROP POLICY IF EXISTS score_insert ON station_scores;
CREATE POLICY score_insert ON station_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id()
   AND examiner_has_station(station_id))
);
DROP POLICY IF EXISTS score_update ON station_scores;
CREATE POLICY score_update ON station_scores FOR UPDATE USING (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id()
   AND examiner_has_station(station_id))
);

-- item_scores (restore 0058)
DROP POLICY IF EXISTS item_score_select ON item_scores;
CREATE POLICY item_score_select ON item_scores FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND EXISTS (
    SELECT 1 FROM checklist_items ci
    JOIN stations st ON st.id = ci.station_id
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE ci.id = item_scores.checklist_item_id
      AND c.department_id = app_department_id()
  )) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
      AND ss.examiner_id = app_user_id()
  ))
);
DROP POLICY IF EXISTS item_score_insert ON item_scores;
CREATE POLICY item_score_insert ON item_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = station_score_id
      AND ss.examiner_id = app_user_id()
  ))
);
DROP POLICY IF EXISTS item_score_update ON item_scores;
CREATE POLICY item_score_update ON item_scores FOR UPDATE USING (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
      AND ss.examiner_id = app_user_id()
  ))
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0058_fix_rls_infinite_recursion'),
    ]

    operations = [
        migrations.RunSQL(sql=FIX_SQL, reverse_sql=REVERSE_SQL),
    ]

    def apply(self, project_state, schema_editor, collect_sql=False):
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            sys.stdout.write(
                "\n  [RLS] Skipping 0059 — not PostgreSQL.\n"
            )
            return project_state
        return super().apply(project_state, schema_editor, collect_sql)

    def unapply(self, project_state, schema_editor, collect_sql=False):
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            return project_state
        return super().unapply(project_state, schema_editor, collect_sql)
