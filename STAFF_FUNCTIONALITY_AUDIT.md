# Staff-Related Functionality Audit – OSCE Project

**Generated:** March 17, 2026  
**Scope:** Complete audit of staff user model, permissions, views, endpoints, and features

---

## 1. Staff User Model & Fields

### User Model: `Examiner` (Custom User)
**File:** [core/models/examiner.py](core/models/examiner.py)

#### Key Fields for Staff:
- **`is_staff`** (BooleanField, default=False) — Django staff flag; determines admin panel access
- **`is_superuser`** (BooleanField, inherited from PermissionsMixin) — Full system access
- **`role`** (CharField, choices: 'examiner', 'coordinator', 'admin') — Custom application role
- **`coordinator_position`** (CharField, choices: 'head', 'rta', 'organizer') — Coordinator tier within a department
- **`department`** (ForeignKey to Department, nullable) — Department assignment for coordinators
- **`is_active`** (BooleanField, default=True) — Account activation status
- **`is_deleted`** (BooleanField, default=False) — Soft-delete flag
- **`allow_multi_login`** (BooleanField, default=False) — Exemption from single-session enforcement
- **`is_dry_user`** (BooleanField, default=False) — Virtual user account for dry marking

#### Computed Properties:
- **`is_admin`** — True only for `role='admin'` (excludes superusers)
- **`is_coordinator`** — True only for `role='coordinator'`
- **`display_name`** — Returns title + full_name (e.g., "Dr. John Smith")

#### User Creation:
- Default `is_staff=True` when creating superusers (via `ExaminerManager.create_superuser()`)
- [Line 26, core/models/examiner.py](core/models/examiner.py#L26)

---

## 2. Staff Roles & Hierarchy

### Role Constants
**File:** [core/models/examiner.py](core/models/examiner.py)

| Role Constant | Value | Role Model Field | Position Field | Global Access | Department Scoped |
|---|---|---|---|---|---|
| `ROLE_EXAMINER` | `'examiner'` | role='examiner' | — | ❌ No | ❌ No |
| `ROLE_COORDINATOR` | `'coordinator'` | role='coordinator' | head/rta/organizer | ❌ No | ✅ Yes |
| `ROLE_ADMIN` | `'admin'` | role='admin' | — | ✅ Yes | ❌ No |
| (Superuser) | — | is_superuser=True | — | ✅ Yes | ❌ No |

### Coordinator Positions
**File:** [core/models/examiner.py](core/models/examiner.py)

| Position | Value | Allowed For | Permissions |
|---|---|---|---|
| Head | `'head'` | Coordinators | View student lists, open dry grading, delete sessions, revert sessions |
| RTA | `'rta'` | Coordinators | Open dry grading |
| Organizer | `'organizer'` | Coordinators | Open dry grading |

---

## 3. Permission System

### Custom Django Permissions
**File:** [core/models/session.py](core/models/session.py) (ExamSession Meta class)

| Permission Codename | Description | Auto-Granted To |
|---|---|---|
| `can_view_student_list` | View student lists | Admin role + Coordinator-Head |
| `can_open_dry_grading` | Open dry grading for a session | Admin + Coordinator-Head + Coordinator-Organizer |
| `can_delete_session` | Archive/delete sessions | Superuser only (manual assignment) |
| `can_revert_session` | Revert completed session to scheduled | Superuser only (manual assignment) |

#### Permission Synchronization
**File:** [core/signals.py](core/signals.py) (signal: `sync_role_permissions`)

Permissions are **auto-synced** on user creation/update:

```python
# can_view_student_list
if user.role == 'admin' or (user.role == 'coordinator' and position == 'head'):
    user_permissions.add(can_view_student_list)

# can_open_dry_grading
if user.role == 'admin' or (user.role == 'coordinator' and position in ('head', 'organizer')):
    user_permissions.add(can_open_dry_grading)
```

---

## 4. Role-Based Permission Classes

**File:** [core/api/permissions.py](core/api/permissions.py)

DRF permission classes enforce role-based access at the API layer:

### Single-Role Permissions:
- **`IsSuperuser`** — Only `is_superuser=True`
- **`IsAdmin`** — Only `role='admin'` (excludes superuser)
- **`IsCoordinator`** — Only `role='coordinator'`
- **`IsCoordinatorHead`** — Only `role='coordinator'` AND `position='head'`
- **`IsExaminer`** — Only `role='examiner'`

### Composite Permissions (OR combinations):
- **`IsSuperuserOrAdmin`** — Superuser OR Admin
- **`IsGlobalOrCoordinator`** — Superuser OR Admin OR any Coordinator
- **`IsGlobalOrCoordinatorHead`** — Superuser OR Admin OR Coordinator-Head only
- **`IsGlobalOrCoordinatorOrAssignedExaminer`** — Superuser OR Admin OR Coordinator OR Examiner (with assignment check)
- **`IsAssignedExaminer`** — Examiner with station assignment

---

## 5. Admin Panel Access

### Authentication Gate
**File:** [core/views.py](core/views.py#L184-L212) (`admin_gateway_view`)

Admin panel requires:
1. **Authenticated user** — Must be logged in
2. **`is_staff=True`** — Must have staff flag set
3. **Secret token** — POST token must match `SECRET_ADMIN_URL` setting
4. **Session unlock** — Sets `session['admin_unlocked']=True`

#### URL Configuration:
- Gateway URL: Set via `SECRET_ADMIN_URL` environment variable (secret path)
- Admin URL: Standard Django admin (`/admin/`)
- Access: Superusers and admins only after unlock

#### Admin Token Injection
**File:** [core/context_processors.py](core/context_processors.py) (`admin_token`)

- **Scope:** Staff/superuser users only — never exposed to examiners
- **Template Variable:** `{{ ADMIN_TOKEN }}`
- **Verification:** [Line 154, templates/creator/base_creator.html](templates/creator/base_creator.html#L154)

#### Django Admin Registration
**File:** [core/admin.py](core/admin.py)

- **ExaminerAdmin:** Full Examiner CRUD (superuser only)
- **Fields displayed:** username, email, full_name, role, title, department, is_staff, is_superuser, groups, permissions
- **Custom actions:**
  - `reset_examiner_password` — Reset to default password (superuser only)
  - `end_sessions` — Terminate user sessions (UserSessionAdmin)

---

## 6. Creator App Views & Features

**Base Layout:** [templates/creator/base_creator.html](templates/creator/base_creator.html)

### Navigation Items (Staff Accessible)

#### All Authenticated Users:
- Dashboard
- Departments
- Courses
- Exams
- Sessions
- Stations
- Paths
- Reports

#### Staff Only (with `can_view_student_list` permission):
- **Student Lists** (conditional: `{% if perms.core.can_view_student_list %}`)
  - [Line 134, templates/creator/base_creator.html](templates/creator/base_creator.html#L134)

#### Superuser/Staff Only:
- **Admin Panel** (conditional: `{% if user.is_staff %}`)
  - Hidden gateway form with admin token
  - [Line 154, templates/creator/base_creator.html](templates/creator/base_creator.html#L154)

### Creator Views Module
**Files:** [creator/views/](creator/views/)

#### Exam Management
- **File:** [creator/views/exams.py](creator/views/exams.py)
- **Can Delete Sessions:** `is_superuser or has_perm('core.can_delete_session')`
- **Features:**
  - Complete exam (locked to admin/head coordinator)
  - Delete exam
  - Restore deleted exam
  - Revert exam completion

#### Session Management
- **File:** [creator/views/sessions.py](creator/views/sessions.py)
- **Features:**
  - Open dry grading: `_can_open_dry_grading()` check
    - Requires: superuser OR admin OR coordinator-head OR coordinator-organizer OR `can_open_dry_grading` permission
    - [Line 32-37, creator/views/sessions.py](creator/views/sessions.py#L32)
  - Delete all sessions (soft delete)
  - Archive/restore sessions
  - Revert completed sessions

#### Station Management
- **File:** [creator/views/stations.py](creator/views/stations.py)
- **Delete Station:** Only head coordinator, admin, or superuser
  - [Line 690, creator/views/stations.py](creator/views/stations.py#L690)

#### Student Management
- **File:** [creator/views/students.py](creator/views/students.py)
- **View Student Lists:** `@permission_required('core.can_view_student_list', raise_exception=True)`
  - [Line 253, creator/views/students.py](creator/views/students.py#L253)
- **Features:**
  - Manage student assignments
  - Delete students
  - Auto-assign paths
  - Redistribute students

---

## 7. Creator API Endpoints

**Base Route:** `/api/creator/`  
**URL Configuration:** [creator/api_urls.py](creator/api_urls.py)

### Courses & ILOs
- **GET** `/api/creator/courses` — List courses (scoped to department)
- **GET** `/api/creator/courses/{id}/ilos` — List ILOs by course
- **GET** `/api/creator/ilos/{id}/library` — Library items by ILO

**File:** [creator/api/courses.py](creator/api/courses.py)

### Exams
- **GET** `/api/creator/exams` — List exams (with optional `?include_deleted=true`)
- **GET** `/api/creator/exams/{id}/stations` — Stations by exam
- **GET** `/api/creator/exams/{id}/summary` — Exam summary
- **DELETE** `/api/creator/exams/{id}` — Soft-delete exam
- **POST** `/api/creator/exams/{id}/restore` — Restore deleted exam
- **POST** `/api/creator/exams/{id}/complete` — Mark exam complete (superuser/admin only)
  - [Line 284, creator/api/exams.py](creator/api/exams.py#L284)
- **POST** `/api/creator/exams/{id}/revert-completion` — Revert completion (superuser/staff only)
  - [Line 198-200, creator/api/exams.py](creator/api/exams.py#L198)

**File:** [creator/api/exams.py](creator/api/exams.py)

### Sessions
- **GET** `/api/creator/sessions/{id}/status` — Check session status
- **POST** `/api/creator/sessions/{id}/activate` — Activate session
- **POST** `/api/creator/sessions/{id}/deactivate` — Deactivate session
- **POST** `/api/creator/sessions/{id}/finish` — Finish session
- **POST** `/api/creator/sessions/{id}/complete` — Complete session
- **DELETE** `/api/creator/sessions/{id}` — Soft-delete session (requires `can_delete_session`)
  - [Line 247-248, creator/api/sessions.py](creator/api/sessions.py#L247)
- **POST** `/api/creator/sessions/{id}/restore` — Restore archived session (requires `can_delete_session`)
  - [Line 311, creator/api/sessions.py](creator/api/sessions.py#L311)
- **POST** `/api/creator/sessions/{id}/hard-delete` — Permanently delete session (superuser only)
- **POST** `/api/creator/sessions/{id}/revert-to-scheduled` — Revert to scheduled (requires `can_revert_session`)
  - [Line 336-345, creator/api/sessions.py](creator/api/sessions.py#L336)

**File:** [creator/api/sessions.py](creator/api/sessions.py)

### Stations
- **DELETE** `/api/creator/stations/{id}` — Delete station

**File:** [creator/api/stations.py](creator/api/stations.py)

### Paths
- **GET** `/api/creator/sessions/{id}/paths` — List paths for session
- **POST** `/api/creator/sessions/{id}/paths/create` — Create path
- **GET** `/api/creator/paths/{id}` — Get path details
- **PUT** `/api/creator/paths/{id}/update` — Update path
- **DELETE** `/api/creator/paths/{id}/delete` — Delete path
- **GET** `/api/creator/paths/{id}/stations` — Stations in path
- **POST** `/api/creator/paths/{id}/stations/add` — Add station to path
- **DELETE** `/api/creator/paths/{id}/stations/{sid}/remove` — Remove station from path
- **POST** `/api/creator/paths/{id}/stations/reorder` — Reorder stations

**File:** [creator/api/paths.py](creator/api/paths.py)

### Library
- **GET** `/api/creator/library` — View question library
- **POST** `/api/creator/library/create` — Create library item
- **DELETE** `/api/creator/library/{id}/delete` — Delete library item

**File:** [creator/api/library.py](creator/api/library.py)

### Examiners (Staff Management)
- **GET** `/api/creator/examiners` — List examiners (department-scoped)
- **POST** `/api/creator/examiners/create` — Create new examiner
- **GET** `/api/creator/sessions/{id}/assignments` — Get examiner assignments for session
- **POST** `/api/creator/sessions/{id}/assignments/create` — Assign examiner to station(s)

**File:** [creator/api/examiners.py](creator/api/examiners.py)

### Students
- **PUT** `/api/creator/students/{id}/path` — Update student path assignment
- **DELETE** `/api/creator/students/{id}` — Delete student
- **DELETE** `/api/creator/sessions/{id}/students` — Delete all students in session
- **POST** `/api/creator/sessions/{id}/redistribute-students` — Redistribute students to paths
- **POST** `/api/creator/sessions/{id}/students/{sid}/assign-path` — Assign student to specific path
- **POST** `/api/creator/sessions/{id}/auto-assign-paths` — Auto-assign students to paths

**File:** [creator/api/students.py](creator/api/students.py)

### Reports & Exports
- **GET** `/api/creator/reports/session/{id}/summary` — Session summary report
- **GET** `/api/creator/reports/session/{id}/students/csv` — Export students to CSV
- **GET** `/api/creator/reports/session/{id}/students/xlsx` — Export students to XLSX
- **GET** `/api/creator/reports/session/{id}/stations/csv` — Export stations/scores to CSV
- **GET** `/api/creator/reports/session/{id}/raw/csv` — Export raw score data to CSV

**File:** [creator/api/reports.py](creator/api/reports.py)

### Statistics
- **GET** `/api/creator/stats/overview` — System statistics overview

**File:** [creator/api/stats.py](creator/api/stats.py)

---

## 8. Core API ViewSets (DRF v2 Layer)

**Base Route:** `/api/`  
**File:** [core/api/views.py](core/api/views.py)

### Department ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** list, retrieve
- **Scope:** Global users see all; coordinators see their department

### Course ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** list, retrieve
- **Scope:** Department-scoped

### Exam ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** list, retrieve, destroy
- **Scope:** Department-scoped

### Exam Session ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** list, retrieve
- **Scope:** Department-scoped

### Path ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** list, retrieve
- **Scope:** Department-scoped

### Station ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinatorOrAssignedExaminer`
- **Methods:** list, retrieve
- **Scope:** Examiners see assigned stations; coordinators see all in department

### Examiner Assignment ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** list, create
- **Scope:** Department-scoped

### Station Score ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinatorOrAssignedExaminer`
- **Methods:** list, create, update, partial_update
- **Scope:** Examiners can write scores for assigned stations

### Department Report ViewSet
- **Permissions:** `IsAuthenticated, IsGlobalOrCoordinator`
- **Methods:** retrieve (summary only)
- **Scope:** Department-scoped reports

---

## 9. Examiner API Views

**File:** [examiner/views/api.py](examiner/views/api.py)

Special endpoints for examiners to bypass assignment checks if staff/superuser:

```python
# Line 76-77: Verify examiner has assignment OR is staff/superuser
if not request.user.is_staff and not request.user.is_superuser:
    # Check assignment
```

**Endpoints where staff users bypass checks:**
- Score submission endpoints
- Checklist submission endpoints
- Status update endpoints

---

## 10. Form Controls for Staff

**File:** [creator/forms.py](creator/forms.py)

### ExaminerCreateForm
**Editableable Fields for Staff:**
- username
- email
- full_name
- title
- department
- is_active
- **is_staff** (checkbox for admin management)

**Password Management:**
- Password (optional, min 8 chars)
- Password confirmation

**Validation:**
- Password match confirmation
- Examiner model constraints (coordinator must have department & position)

---

## 11. Admin Interface Features

**File:** [core/admin.py](core/admin.py)

### User Management (ExaminerAdmin)
- **List Display:** username, email, full_name, role, title, department, is_active, password_status, is_deleted, is_staff
- **List Filters:** role, is_active, is_deleted, is_staff, department
- **Search Fields:** username, email, full_name
- **Inline Admin:** UserProfileInline (password_changed_at tracking)

### Custom Admin Actions
1. **Reset Password to Default**
   - Action: `reset_examiner_password` (superuser only)
   - Sets `must_change_password=True`
   - Sets `password_changed_at=None`
   - Logs audit entry
   - [Line 107-137, core/admin.py](core/admin.py#L107)

2. **End User Sessions**
   - Action: `end_sessions` (UserSessionAdmin, superuser only)
   - Deletes Django session records
   - Deletes UserSession rows
   - Logs audit entry
   - [Line 89-103, core/admin.py](core/admin.py#L89)

### User Session Management (UserSessionAdmin)
- **List Display:** user, session_key, created_at, is_alive
- **Actions:** End selected sessions
- **Read-only Fields:** user, session_key, created_at
- **No Add Permission** — Sessions created by login flow only

---

## 12. Audit & Logging

### Login Audit
**File:** [core/models/audit.py](core/models/audit.py)

- Logs all login events with timestamp, IP, user, role
- Tracks session lifecycle

### Admin Access Logging
**File:** [core/views.py](core/views.py#L210-211)

```python
log_action(request, 'ADMIN_ACCESS', 'User', request.user.id,
           f'{request.user.display_name} unlocked admin panel')
```

### Password Reset Logging
**File:** [core/admin.py](core/admin.py#L131)

```python
audit_logger.warning(
    "Admin '%s' reset password for examiner '%s'.",
    request.user.username, examiner.username,
)
```

---

## 13. Department Scoping

### Global Access Roles (No Department Scope)
- **Superuser** — `is_superuser=True`
- **Admin** — `role='admin'`

### Department-Scoped Roles
- **Coordinator** — `role='coordinator'`, must have `department` assigned
- **Examiner** — `role='examiner'`, limited to assigned stations

**Helper Functions:** [core/utils/roles.py](core/utils/roles.py)

```python
def is_global(user):
    """Superuser or Admin — cross-department access."""
    return is_superuser(user) or is_admin(user)

def get_user_department(user):
    """Return Department for scoping, or None for global access."""
    if is_global(user):
        return None  # global access
    if is_coordinator(user):
        return user.department
    return None
```

---

## 14. Security Controls & Checks

### Authentication Requirements
- All non-login views require `@login_required`
- API endpoints require `IsAuthenticated` as base permission

### Role-Based Gates
- `@permission_required('core.can_view_student_list')` for student lists
- `is_staff` checks for admin panel access
- `has_perm('core.can_delete_session')` for session deletion
- `has_perm('core.can_revert_session')` for session reversion
- `has_perm('core.can_open_dry_grading')` for dry marking

### Security Fixes Applied
**File:** [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md)

- **VULN-008 (Fixed):** Changed `is_staff` → `is_superuser` in three examiner API endpoints
  - Reason: `is_staff` only means "can access admin site", not superuser privilege
  - Files affected: [examiner/views/api.py](examiner/views/api.py#L77)

- **Admin Token Scoping:** Never exposed to examiner templates
  - [core/context_processors.py](core/context_processors.py#L14)

---

## 15. User Roles Summary Table

| Feature | Superuser | Admin | Coordinator-Head | Coordinator-RTA | Coordinator-Organizer | Examiner |
|---|---|---|---|---|---|---|
| **Access Level** | Global | Global | Department | Department | Department | Station |
| **is_staff** | ✅ Yes | ✅ Yes | Optional | Optional | Optional | No |
| **Admin Panel** | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **View Departments** | ✅ All | ✅ All | ✅ Own | ✅ Own | ✅ Own | ❌ None |
| **View Courses** | ✅ All | ✅ All | ✅ Own Dept | ✅ Own Dept | ✅ Own Dept | ❌ None |
| **View Exams** | ✅ All | ✅ All | ✅ Own Dept | ✅ Own Dept | ✅ Own Dept | ❌ None |
| **Manage Sessions** | ✅ All | ✅ All | ✅ Own Dept | ✅ Own Dept | ✅ Own Dept | ❌ None |
| **View Student Lists** | ✅ All | ✅ All | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Open Dry Grading** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes | ❌ No |
| **Delete Sessions** | ✅ Yes | ❌ Manual | ❌ Manual | ❌ Manual | ❌ Manual | ❌ No |
| **Revert Sessions** | ✅ Yes | ❌ Manual | ❌ Manual | ❌ Manual | ❌ Manual | ❌ No |
| **Delete Exams** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Delete Stations** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Create Examiners** | ✅ Yes | ✅ Yes | ✅ Own Dept | ❌ No | ❌ No | ❌ No |
| **Reset Passwords** | ✅ Yes (Admin) | ✅ Yes (Admin) | ❌ No | ❌ No | ❌ No | ❌ No |
| **Assign Examiners** | ✅ Yes | ✅ Yes | ✅ Own Dept | ❌ No | ❌ No | ❌ No |
| **View Reports** | ✅ All | ✅ All | ✅ Own Dept | ✅ Own Dept | ✅ Own Dept | ✅ Assigned |
| **Score Writing** | ✅ Any | ✅ Any | ✅ Any | ✅ Any | ✅ Any | ✅ Assigned |

---

## 16. Environment Variables Related to Staff/Admin

**File:** [.env.example](.env.example)

```bash
# Admin & Security
# SECRET_ADMIN_URL=my-secret-admin-path
```

- **SECRET_ADMIN_URL** — Secret path for admin gateway validation and token

---

## 17. Templates Using Staff Checks

### base_creator.html
- [Line 134](templates/creator/base_creator.html#L134): Student Lists menu (conditional on `perms.core.can_view_student_list`)
- [Line 154](templates/creator/base_creator.html#L154): Admin Panel button (conditional on `user.is_staff`)

### exams/detail.html
- [Line 60](templates/creator/exams/detail.html#L60): Delete exam button (conditional on `is_superuser or is_staff`)

### sessions/detail.html
- [Line 109](templates/creator/sessions/detail.html#L109): Revert session button (conditional on `is_superuser or perms.core.can_revert_session`)
- [Line 118](templates/creator/sessions/detail.html#L118): Delete session button (conditional on `is_superuser or is_staff`)

---

## Summary

Staff users in the OSCE system include:
- **Superusers** — Complete system access, full Django admin
- **Admins** — Global access to all departments, manage exams/sessions/users
- **Coordinators** — Department-scoped access, user management, dry grading
  - **Head** — Can view student lists, delete stations, revert sessions
  - **RTA** — Can open dry grading
  - **Organizer** — Can open dry grading

All staff users are marked with `is_staff=True` (except coordinators, which is optional), giving them access to:
- Admin panel (with SECRET_ADMIN_URL token validation)
- Creator app full interface
- Department scoping applied automatically
- Permission-based features (student lists, dry grading, session control)
- Audit logging of all actions
