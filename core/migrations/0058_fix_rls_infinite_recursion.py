"""
Fix RLS infinite recursion on ALL tables.

Root cause: FORCE ROW LEVEL SECURITY is enabled on all tables, and
the helper functions (exam_department_id, session_department_id,
path_department_id, station_department_id) query the SAME table
whose policy calls them.  Even with SECURITY DEFINER, FORCE RLS
still applies → the policy fires inside the function → calls the
function again → infinite recursion.

Fix: rewrite EVERY policy that uses a self-referencing helper
function to use an inline subquery that references ONLY parent
tables (never the same table).  The chain always terminates at
`courses`, whose coordinator policy is a simple column comparison.
"""
import sys
from django.db import migrations


FIX_SQL = """
-- ════════════════════════════════════════════════════════════════
-- EXAMS — all 4 policies rewritten
-- Old: exam_department_id(id)  →  queries exams  →  recursion!
-- New: inline subquery to courses only
-- ════════════════════════════════════════════════════════════════
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
-- EXAM_SESSIONS — all 4 policies rewritten
-- Old: session_department_id(id)  →  queries exam_sessions  →  recursion!
-- New: inline via exams → courses (parent tables only)
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS session_select ON exam_sessions;
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exams e JOIN courses c ON c.id = e.course_id
    WHERE e.id = exam_sessions.exam_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM examiner_assignments ea
    WHERE ea.session_id = exam_sessions.id
      AND ea.examiner_id = app_user_id()
  ))
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
-- PATHS — all 4 policies rewritten
-- Old: path_department_id(id)  →  queries paths  →  recursion!
-- New: inline via exam_sessions → exams → courses
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS path_select ON paths;
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM exam_sessions es
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
-- STATIONS — all 4 policies rewritten
-- Old: station_department_id(id)  →  queries stations  →  recursion!
-- New: inline via paths → exam_sessions → exams → courses
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS station_select ON stations;
CREATE POLICY station_select ON stations FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM paths p
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE p.id = stations.path_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(id))
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
-- CHECKLIST_ITEMS — all 4 policies rewritten
-- Old: station_department_id(station_id)  →  queries stations
--      whose policy called station_department_id(id)  →  recursion!
-- New: inline via stations → paths → exam_sessions → exams → courses
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS checklist_select ON checklist_items;
CREATE POLICY checklist_select ON checklist_items FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = checklist_items.station_id
  ) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(station_id))
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
-- EXAMINER_ASSIGNMENTS — all 4 policies rewritten
-- Old: station_department_id(station_id)  →  same chain  →  recursion!
-- New: inline via stations → paths → exam_sessions → exams → courses
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS assign_select ON examiner_assignments;
CREATE POLICY assign_select ON examiner_assignments FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND (
    SELECT c.department_id
    FROM stations st
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE st.id = examiner_assignments.station_id
  ) = app_department_id()) OR
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
-- STATION_SCORES — coordinator policies rewritten
-- Old: station_department_id(station_id)  →  recursion chain
-- New: inline via stations → paths → exam_sessions → exams → courses
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS score_select ON station_scores;
CREATE POLICY score_select ON station_scores FOR SELECT USING (
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

DROP POLICY IF EXISTS score_delete ON station_scores;
CREATE POLICY score_delete ON station_scores FOR DELETE USING (is_global_role());


-- ════════════════════════════════════════════════════════════════
-- ITEM_SCORES — coordinator policies rewritten
-- Old: station_department_id(ci.station_id)  →  recursion chain
-- New: inline via checklist_items → stations → … → courses
-- ════════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS item_score_select ON item_scores;
CREATE POLICY item_score_select ON item_scores FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND EXISTS (
    SELECT 1
    FROM checklist_items ci
    JOIN stations st ON st.id = ci.station_id
    JOIN paths p ON p.id = st.path_id
    JOIN exam_sessions es ON es.id = p.session_id
    JOIN exams e ON e.id = es.exam_id
    JOIN courses c ON c.id = e.course_id
    WHERE ci.id = item_scores.checklist_item_id
      AND c.department_id = app_department_id()
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

DROP POLICY IF EXISTS item_score_insert ON item_scores;
CREATE POLICY item_score_insert ON item_scores FOR INSERT WITH CHECK (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = station_score_id
    AND ss.examiner_id = app_user_id()
  ) AND EXISTS (
    SELECT 1 FROM checklist_items ci
    WHERE ci.id = checklist_item_id
    AND examiner_has_station(ci.station_id)
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

DROP POLICY IF EXISTS item_score_delete ON item_scores;
CREATE POLICY item_score_delete ON item_scores FOR DELETE USING (is_global_role());
"""


REVERSE_SQL = """
-- Revert exams to 0051 style (with exam_department_id)
DROP POLICY IF EXISTS exam_select ON exams;
CREATE POLICY exam_select ON exams FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM exam_sessions es
    JOIN examiner_assignments ea ON ea.session_id = es.id
    WHERE es.exam_id = exams.id AND ea.examiner_id = app_user_id()
  ))
);
DROP POLICY IF EXISTS exam_insert ON exams;
CREATE POLICY exam_insert ON exams FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS exam_update ON exams;
CREATE POLICY exam_update ON exams FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS exam_delete ON exams;
CREATE POLICY exam_delete ON exams FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND exam_department_id(id) = app_department_id())
);

-- Revert exam_sessions
DROP POLICY IF EXISTS session_select ON exam_sessions;
CREATE POLICY session_select ON exam_sessions FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM examiner_assignments ea
    WHERE ea.session_id = exam_sessions.id AND ea.examiner_id = app_user_id()
  ))
);
DROP POLICY IF EXISTS session_insert ON exam_sessions;
CREATE POLICY session_insert ON exam_sessions FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS session_update ON exam_sessions;
CREATE POLICY session_update ON exam_sessions FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS session_delete ON exam_sessions;
CREATE POLICY session_delete ON exam_sessions FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND session_department_id(id) = app_department_id())
);

-- Revert paths
DROP POLICY IF EXISTS path_select ON paths;
CREATE POLICY path_select ON paths FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM stations st
    JOIN examiner_assignments ea ON ea.station_id = st.id
    WHERE st.path_id = paths.id AND ea.examiner_id = app_user_id()
  ))
);
DROP POLICY IF EXISTS path_insert ON paths;
CREATE POLICY path_insert ON paths FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS path_update ON paths;
CREATE POLICY path_update ON paths FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS path_delete ON paths;
CREATE POLICY path_delete ON paths FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND path_department_id(id) = app_department_id())
);

-- Revert stations
DROP POLICY IF EXISTS station_select ON stations;
CREATE POLICY station_select ON stations FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(id))
);
DROP POLICY IF EXISTS station_insert ON stations;
CREATE POLICY station_insert ON stations FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS station_update ON stations;
CREATE POLICY station_update ON stations FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);
DROP POLICY IF EXISTS station_delete ON stations;
CREATE POLICY station_delete ON stations FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(id) = app_department_id())
);

-- Revert checklist_items
DROP POLICY IF EXISTS checklist_select ON checklist_items;
CREATE POLICY checklist_select ON checklist_items FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_has_station(station_id))
);
DROP POLICY IF EXISTS checklist_insert ON checklist_items;
CREATE POLICY checklist_insert ON checklist_items FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
DROP POLICY IF EXISTS checklist_update ON checklist_items;
CREATE POLICY checklist_update ON checklist_items FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
DROP POLICY IF EXISTS checklist_delete ON checklist_items;
CREATE POLICY checklist_delete ON checklist_items FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);

-- Revert examiner_assignments
DROP POLICY IF EXISTS assign_select ON examiner_assignments;
CREATE POLICY assign_select ON examiner_assignments FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id()) OR
  (app_role() = 'EXAMINER' AND examiner_id = app_user_id())
);
DROP POLICY IF EXISTS assign_insert ON examiner_assignments;
CREATE POLICY assign_insert ON examiner_assignments FOR INSERT WITH CHECK (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
DROP POLICY IF EXISTS assign_update ON examiner_assignments;
CREATE POLICY assign_update ON examiner_assignments FOR UPDATE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);
DROP POLICY IF EXISTS assign_delete ON examiner_assignments;
CREATE POLICY assign_delete ON examiner_assignments FOR DELETE USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id())
);

-- Revert station_scores
DROP POLICY IF EXISTS score_select ON station_scores;
CREATE POLICY score_select ON station_scores FOR SELECT USING (
  is_global_role() OR
  (is_coordinator() AND station_department_id(station_id) = app_department_id()) OR
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
DROP POLICY IF EXISTS score_delete ON station_scores;
CREATE POLICY score_delete ON station_scores FOR DELETE USING (is_global_role());

-- Revert item_scores
DROP POLICY IF EXISTS item_score_select ON item_scores;
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
DROP POLICY IF EXISTS item_score_insert ON item_scores;
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
DROP POLICY IF EXISTS item_score_update ON item_scores;
CREATE POLICY item_score_update ON item_scores FOR UPDATE USING (
  is_global_role() OR
  (app_role() = 'EXAMINER' AND EXISTS (
    SELECT 1 FROM station_scores ss
    WHERE ss.id = item_scores.station_score_id
    AND ss.examiner_id = app_user_id()
  ))
);
DROP POLICY IF EXISTS item_score_delete ON item_scores;
CREATE POLICY item_score_delete ON item_scores FOR DELETE USING (is_global_role());
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_fix_rls_coordinator_insert'),
    ]

    operations = [
        migrations.RunSQL(sql=FIX_SQL, reverse_sql=REVERSE_SQL),
    ]

    def apply(self, project_state, schema_editor, collect_sql=False):
        """Skip on non-PostgreSQL databases."""
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            import sys
            sys.stdout.write(
                "\n  [RLS] Skipping 0058 — not PostgreSQL.\n"
            )
            return project_state
        return super().apply(project_state, schema_editor, collect_sql)

    def unapply(self, project_state, schema_editor, collect_sql=False):
        db_engine = schema_editor.connection.vendor
        if db_engine != 'postgresql':
            return project_state
        return super().unapply(project_state, schema_editor, collect_sql)
