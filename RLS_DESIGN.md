# Row-Level Security (RLS) Design Document

**Platform:** OSCE Clinical Exam Platform  
**Database:** PostgreSQL 14+ with Django 5.2  
**Last updated:** 2026-03-04

---

## 1. Core Concept: How Django Roles Reach RLS

PostgreSQL RLS operates at the DB connection level, not the Django user
level. Since Django connects to PostgreSQL as a single DB user, RLS
cannot distinguish between a Superuser and a Coordinator unless Django
explicitly passes role context into the DB session.

### Solution — PostgreSQL Session Variables

Django injects 4 variables at the start of every request via
`RLSSessionMiddleware` (in `core/middleware.py`):

| Variable               | Type    | Description                              |
|------------------------|---------|------------------------------------------|
| `app.current_user_id`  | INTEGER | PK of the authenticated Django user      |
| `app.current_role`     | TEXT    | Role string (see constants below)        |
| `app.department_id`    | BIGINT  | Department PK (coordinators only)        |
| `app.station_ids`      | TEXT    | Comma-separated station UUIDs (examiners)|

### Role Constants

| Constant                | Maps From (Django Examiner model)           |
|-------------------------|---------------------------------------------|
| `SUPERUSER`             | `is_superuser = True`                       |
| `ADMIN`                 | `role = 'admin'`                            |
| `COORDINATOR_HEAD`      | `role = 'coordinator', position = 'head'`   |
| `COORDINATOR_ORGANIZER` | `role = 'coordinator', position = 'organizer'` |
| `COORDINATOR_RTA`       | `role = 'coordinator', position = 'rta'`    |
| `EXAMINER`              | `role = 'examiner'`                         |
| `ANONYMOUS`             | Unauthenticated request                     |

### Middleware Configuration

```python
# osce_project/settings/base.py — MIDDLEWARE list
'core.middleware.RLSSessionMiddleware',  # After AuthenticationMiddleware
```

The middleware uses `set_config(..., true)` so all variables are
**transaction-scoped** and reset automatically after each request.
For unauthenticated users: role = `'ANONYMOUS'`, all others = `''`.

---

## 2. Data Hierarchy & Table Mapping

```
Department (departments)           PK: BigAutoField (integer)
└── Course (courses)               PK: AutoField (integer), FK → departments
    └── Exam (exams)               PK: UUIDField, FK → courses
        └── ExamSession (exam_sessions)  PK: UUIDField, FK → exams
            └── Path (paths)             PK: UUIDField, FK → exam_sessions
                └── Station (stations)   PK: UUIDField, FK → paths
                    ├── ChecklistItem (checklist_items)   PK: AutoField, FK → stations
                    ├── ExaminerAssignment (examiner_assignments)  PK: UUIDField, FK → stations
                    ├── StationScore (station_scores)     PK: UUIDField, FK → stations
                    └── ItemScore (item_scores)           PK: UUIDField, FK → checklist_items
```

**Department resolution path (for RLS):**
- `Course.department_id` → `departments.id`  (direct FK)
- `Exam` → `courses.department_id` (via `exams.course_id`)
- `ExamSession` → `exams` → `courses.department_id`
- `Path` → `exam_sessions` → `exams` → `courses.department_id`
- `Station` → `paths` → `exam_sessions` → `exams` → `courses.department_id`

**Note:** `Exam.department` is a **CharField** (text), not a FK. RLS traces
department through `Exam → Course.department_id` instead.

### Coordinator Assignment

Coordinators are assigned directly on the `Examiner` model:
- `coordinator_department` FK → `departments`
- `coordinator_position`: `'head'` / `'rta'` / `'organizer'`

(No separate `DepartmentCoordinator` table exists.)

---

## 3. PostgreSQL Helper Functions

All helper functions are created in migration `0027_rls_policies.py`.
Policies use **only** these helpers — never inline `current_setting()`.

### Role Functions

```sql
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

-- Returns TRUE if role is any Coordinator type
CREATE OR REPLACE FUNCTION is_coordinator()
RETURNS BOOLEAN AS $$
  SELECT app_role() IN (
    'COORDINATOR_HEAD',
    'COORDINATOR_ORGANIZER',
    'COORDINATOR_RTA'
  )
$$ LANGUAGE sql STABLE SECURITY DEFINER;
```

### Identity Functions

```sql
-- Returns current user's department_id as BIGINT
CREATE OR REPLACE FUNCTION app_department_id()
RETURNS BIGINT AS $$
  SELECT NULLIF(current_setting('app.department_id', TRUE), '')::BIGINT
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Returns current user's PK as INTEGER
CREATE OR REPLACE FUNCTION app_user_id()
RETURNS INTEGER AS $$
  SELECT NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER
$$ LANGUAGE sql STABLE SECURITY DEFINER;
```

### Hierarchy Traversal Functions

```sql
-- Station → Path → Session → Exam → Course → Department
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

-- Exam → Course → Department
CREATE OR REPLACE FUNCTION exam_department_id(p_exam_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   exams ex JOIN courses c ON c.id = ex.course_id
  WHERE  ex.id = p_exam_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Session → Exam → Course → Department
CREATE OR REPLACE FUNCTION session_department_id(p_session_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   exam_sessions se
  JOIN   exams ex ON ex.id = se.exam_id
  JOIN   courses c ON c.id = ex.course_id
  WHERE  se.id = p_session_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Path → Session → Exam → Course → Department
CREATE OR REPLACE FUNCTION path_department_id(p_path_id UUID)
RETURNS BIGINT AS $$
  SELECT c.department_id
  FROM   paths pa
  JOIN   exam_sessions se ON se.id = pa.session_id
  JOIN   exams ex ON ex.id = se.exam_id
  JOIN   courses c ON c.id = ex.course_id
  WHERE  pa.id = p_path_id
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Examiner assignment check
CREATE OR REPLACE FUNCTION examiner_has_station(p_station_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM examiner_assignments
    WHERE station_id  = p_station_id
    AND   examiner_id = app_user_id()
  )
$$ LANGUAGE sql STABLE SECURITY DEFINER;
```

---

## 4. RLS Policies by Table

All tables have `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.

### 4.1 departments

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all rows; `is_coordinator()` → `id = app_department_id()` only; EXAMINER/ANONYMOUS → no rows |
| INSERT    | `is_global_role()` only |
| UPDATE    | `is_global_role()` only |
| DELETE    | `is_global_role()` only |

### 4.2 courses

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `department_id = app_department_id()` |
| INSERT    | `is_global_role()` or coordinator (own dept) |
| UPDATE    | `is_global_role()` or coordinator (own dept) |
| DELETE    | `is_global_role()` or coordinator (own dept) |

### 4.3 exams

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `exam_department_id(id) = app_department_id()` |
| INSERT    | `is_global_role()` or coordinator (own dept) |
| UPDATE    | `is_global_role()` or coordinator (own dept) |
| DELETE    | `is_global_role()` or coordinator (own dept) — **Django view further restricts soft-delete/archive to Superuser, Admin, and Coordinator-Head only** |

### 4.4 exam_sessions

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `session_department_id(id) = app_department_id()` |
| INSERT/UPDATE/DELETE | `is_global_role()` or coordinator (own dept) |

### 4.5 paths

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `path_department_id(id) = app_department_id()` |
| INSERT/UPDATE/DELETE | `is_global_role()` or coordinator (own dept) |

### 4.6 stations

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `station_department_id(id) = app_department_id()`; `EXAMINER` → `examiner_has_station(id)` |
| INSERT/UPDATE/DELETE | `is_global_role()` or coordinator (own dept) |

### 4.7 checklist_items

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `station_department_id(station_id) = app_department_id()`; `EXAMINER` → `examiner_has_station(station_id)` |
| INSERT/UPDATE/DELETE | `is_global_role()` or coordinator (own dept) |

### 4.8 examiner_assignments

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → `station_department_id(station_id) = app_department_id()`; `EXAMINER` → `examiner_id = app_user_id()` |
| INSERT/UPDATE/DELETE | `is_global_role()` or coordinator (own dept) |

### 4.9 station_scores

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → via `station_department_id(station_id)`; `EXAMINER` → own scores on assigned stations only |
| INSERT    | `is_global_role()` or EXAMINER (own, assigned station only) |
| UPDATE    | `is_global_role()` or EXAMINER (own scores only) |
| DELETE    | `is_global_role()` only |

### 4.10 item_scores

| Operation | Policy |
|-----------|--------|
| SELECT    | `is_global_role()` → all; `is_coordinator()` → via station dept join; `EXAMINER` → own scores on assigned stations |
| INSERT    | `is_global_role()` or EXAMINER (own, assigned station) |
| UPDATE    | `is_global_role()` or EXAMINER (own scores) |
| DELETE    | `is_global_role()` only |

---

## 5. Migration Files

| Migration | Purpose |
|-----------|---------|
| `0027_rls_policies.py` | All helper functions + ENABLE/FORCE RLS + all CREATE POLICY statements |

The migration auto-skips on SQLite (development) and only runs on PostgreSQL.
Reverse SQL is provided for all operations for clean rollback.

---

## 6. Critical Notes

### Superuser Bypass Warning

PostgreSQL's built-in `SUPERUSER` role **bypasses all RLS policies**.
The Django application MUST connect with a **non-superuser** database
role for RLS to take effect. Create a dedicated role:

```sql
CREATE ROLE osce_app LOGIN PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO osce_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO osce_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO osce_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO osce_app;
-- osce_app is NOT a superuser, so RLS policies apply to it
```

### FORCE ROW LEVEL SECURITY

All tables use `FORCE ROW LEVEL SECURITY` so that even the table owner
is subject to RLS policies. This prevents accidental bypass if the app
connects as the table owner.

### Performance Considerations

The hierarchy traversal functions (`station_department_id`, etc.) perform
JOINs. For high-traffic tables, consider:

1. Adding a denormalised `department_id` column to `stations`
2. Keeping it in sync via triggers or application code
3. This avoids the multi-join traversal on every row access

### Transaction Scope

All session variables use `set_config(..., true)` which makes them
**transaction-scoped**. They reset after each request. Variables cannot
leak between requests, even with connection pooling.

---

## 7. Testing Strategy

### Test Matrix

| # | Test Case | Expected Result |
|---|-----------|-----------------|
| 1 | SUPERUSER session → SELECT all tables | All rows visible |
| 2 | ADMIN session → SELECT all tables | All rows visible |
| 3 | COORDINATOR (Dept A) → SELECT courses | Only Dept A courses |
| 4 | COORDINATOR (Dept A) → SELECT exams | Only Dept A exams (via course) |
| 5 | COORDINATOR (Dept A) → SELECT stations Dept B | Zero rows |
| 6 | EXAMINER → SELECT stations (unassigned) | Zero rows |
| 7 | EXAMINER → SELECT stations (assigned) | Only assigned stations |
| 8 | EXAMINER → INSERT station_score (assigned, active session) | Success |
| 9 | EXAMINER → INSERT station_score (unassigned station) | Blocked |
| 10 | ANONYMOUS → SELECT any table | Zero rows |
| 11 | FORCE RLS → connect as table owner | Policies still apply |

### How to Test

```sql
-- Set session as Coordinator of Department 1
SELECT set_config('app.current_user_id', '5', true);
SELECT set_config('app.current_role', 'COORDINATOR_HEAD', true);
SELECT set_config('app.department_id', '1', true);
SELECT set_config('app.station_ids', '', true);

-- Should only return Department 1 courses
SELECT * FROM courses;

-- Switch to ANONYMOUS
SELECT set_config('app.current_role', 'ANONYMOUS', true);
SELECT set_config('app.current_user_id', '', true);
SELECT set_config('app.department_id', '', true);

-- Should return 0 rows
SELECT * FROM courses;
```

---

## 8. Deployment Checklist

- [ ] Create non-superuser PostgreSQL role for the Django app
- [ ] Update `DATABASES` settings with non-superuser credentials
- [ ] Run `python manage.py migrate` (applies 0027_rls_policies)
- [ ] Verify helper functions exist: `SELECT app_role();`
- [ ] Verify RLS is enabled: `SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'courses';`
- [ ] Verify policies exist: `SELECT * FROM pg_policies WHERE schemaname = 'public';`
- [ ] Run the test matrix above
- [ ] Monitor query performance — add indexes if traversal is slow
- [ ] Confirm connection pooler (PgBouncer) uses transaction mode (session vars reset per transaction)
