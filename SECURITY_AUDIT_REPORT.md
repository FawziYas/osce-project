# Security Audit Report — SQL Injection & Data Leakage
**Date:** March 13, 2026  
**Django Version:** 5.2.11 | DRF 3.16.1  
**Database:** PostgreSQL with Row-Level Security (RLS)  
**Authentication:** Session-based (no JWT/CORS)  
**Project:** OSCE Examination System  
**Scope:** Comprehensive SQL injection, IDOR, broken access control, and data leakage audit  
**Status:** ✅ All identified vulnerabilities fixed

---

## 1. Executive Summary

A deep security audit was performed across the entire codebase — both the legacy v1 API layer (`creator/api/`, `examiner/api/`) and the v2 DRF layer (`core/api/`). Three automated sub-agents scanned all source files for SQL injection, data leakage / IDOR, and authentication/settings weaknesses.

### Severity Summary

| Severity | Found | Fixed | Remaining |
|----------|-------|-------|-----------|
| **CRITICAL** | 2 | 2 | 0 |
| **HIGH** | 5 | 5 | 0 |
| **MEDIUM** | 6 | 6 | 0 |
| **LOW** | 3 | 0 | 3 (accepted risk) |
| **Total** | **16** | **13** | **3** |

**SQL Injection:** No vulnerabilities found. All database access uses the Django ORM with parameterized queries. No `.raw()`, `.extra()`, or string-interpolated SQL anywhere in the codebase.

**Data Leakage / Broken Access Control:** CRITICAL findings. The entire v1 creator API layer (10+ files, 45+ endpoints) had zero department-scoping — any authenticated coordinator could read and modify data across all departments.

---

## 2. Vulnerability Details

### VULN-001: Soft-Deleted Users Can Authenticate
- **ID:** VULN-001
- **Severity:** CRITICAL
- **Category:** Authentication Bypass (CWE-287)
- **Location:** `core/views.py` → `login_view()`
- **Description:** Users with `is_deleted=True` (soft-deleted) could still authenticate via the login form. Django's `authenticate()` does not check custom soft-delete flags.
- **Attack Scenario:** A terminated examiner whose account was soft-deleted could log back in and access the system with their previous role and permissions.
- **Impact:** Full access restoration for deactivated users; violates principle of least privilege.
- **Fix Applied:** Added `is_deleted` check immediately after `authenticate()` succeeds.

```python
# BEFORE (vulnerable)
user = authenticate(request, username=username, password=password)
if user is not None:
    login(request, user)
    ...

# AFTER (fixed)
user = authenticate(request, username=username, password=password)
if user is not None:
    if getattr(user, 'is_deleted', False):
        messages.error(request, 'Invalid credentials.')
        return render(request, 'login.html', {'form': form})
    login(request, user)
    ...
```

---

### VULN-002: Creator API — Zero Department Scoping (10 Files, 45+ Endpoints)
- **ID:** VULN-002
- **Severity:** CRITICAL
- **Category:** Broken Access Control / IDOR (CWE-639)
- **Location:** All files in `creator/api/`:
  - `courses.py` — courses, ILOs, checklist library
  - `examiners.py` — examiner list, session assignments
  - `exams.py` — exam CRUD, station items, summary
  - `sessions.py` — session lifecycle (activate, deactivate, finish, delete, etc.)
  - `stations.py` — station delete
  - `students.py` — student CRUD, rotation, status
  - `stats.py` — dashboard statistics
  - `paths.py` — path CRUD, station management
  - `library.py` — checklist library CRUD
  - `reports.py` — session reports, CSV/XLSX exports
- **Description:** Every `get_object_or_404()` and `Model.objects.filter()` call in the v1 creator API used only the object's primary key with no department filtering. The `scope_queryset()` helper (already available in `core/utils/roles.py`) was not used anywhere in the v1 API layer.
- **Attack Scenario:** Coordinator A (Department of Surgery) could call `GET /api/creator/sessions/` and see all sessions across Medicine, Pediatrics, etc. They could also `DELETE` exams, export student data, or modify paths belonging to other departments.
- **Impact:** Complete cross-department data exposure and modification. Any coordinator could access, export, or delete data from every department.
- **Fix Applied:** Added `scope_queryset()` calls to all 45+ endpoints across all 10 files. Created `_scoped_session()`, `_scoped_student()`, and `_scoped_path()` helper functions where needed.

```python
# BEFORE (vulnerable) — repeated across all 10 files
session = get_object_or_404(ExamSession, pk=session_id)

# AFTER (fixed)
from core.utils.roles import scope_queryset

def _scoped_session(user):
    return scope_queryset(user, ExamSession.objects.all(),
                         dept_field='exam__course__department')

session = get_object_or_404(_scoped_session(request.user), pk=session_id)
```

---

### VULN-003: Creator Views — Examiner List/Detail Not Scoped
- **ID:** VULN-003
- **Severity:** HIGH
- **Category:** Broken Access Control (CWE-862)
- **Location:** `creator/views/examiners.py` → `examiner_list()`, `examiner_detail()`, `examiner_edit()`
- **Description:** Template views for examiner management returned all examiners globally without filtering by the coordinator's department.
- **Impact:** Coordinators could view and edit examiners from other departments.
- **Fix Applied:** Added `scope_queryset()` to all three views with `dept_field='coordinator_department'`.

---

### VULN-004: IDOR in StationScore Creation (v2 API)
- **ID:** VULN-004
- **Severity:** HIGH
- **Category:** IDOR (CWE-639)
- **Location:** `core/api/views.py` → `StationScoreViewSet.perform_create()`
- **Description:** When creating a `StationScore`, the API accepted a `session_student` ID and a `session` ID without cross-validating that the student actually belongs to that session.
- **Attack Scenario:** An examiner could submit scores for a student who is not enrolled in their session by crafting a request with a mismatched `session_student_id` from a different session.
- **Impact:** Score injection into incorrect sessions; data integrity compromise.
- **Fix Applied:** Added cross-validation: `if session and str(session_student.session_id) != str(session.pk): raise ValidationError(...)`.

---

### VULN-005: Open Redirect in 3 Locations
- **ID:** VULN-005
- **Severity:** HIGH
- **Category:** Open Redirect (CWE-601)
- **Location:**
  - `creator/views/examiners.py` → `examiner_unassign()`
  - `creator/views/courses.py` → `course_create()`
  - `creator/views/courses.py` → `course_edit()`
- **Description:** All three views used `request.GET.get('next', ...)` or `request.POST.get('next', ...)` for redirect targets without validating the URL is same-origin.
- **Attack Scenario:** Attacker crafts a link like `/creator/courses/create/?next=https://evil.com/steal-session`, user submits the form, and is redirected to the attacker's site.
- **Impact:** Phishing attacks, session credential theft.
- **Fix Applied:** Added `url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()})` validation to all three locations.

```python
# BEFORE (vulnerable)
next_url = request.GET.get('next', reverse('creator:examiner_list'))
return redirect(next_url)

# AFTER (fixed)
from django.utils.http import url_has_allowed_host_and_scheme
next_url = request.GET.get('next', '')
if not next_url or not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
    next_url = reverse('creator:examiner_list')
return redirect(next_url)
```

---

### VULN-006: Creator API Stats — Global Counts Across Departments
- **ID:** VULN-006
- **Severity:** HIGH
- **Category:** Information Disclosure (CWE-200)
- **Location:** `creator/api/stats.py` → `get_stats()`
- **Description:** All 9 statistics counters (courses, ILOs, exams, sessions, students, examiners, stations, paths, library items) returned global counts across all departments.
- **Impact:** Coordinators could see aggregate data revealing the size and structure of other departments' exam programs.
- **Fix Applied:** All 9 counters now use `scope_queryset()` with appropriate department field chains.

---

### VULN-007: Creator API Examiners — Cross-Department Assignment
- **ID:** VULN-007
- **Severity:** HIGH
- **Category:** Broken Access Control (CWE-862)
- **Location:** `creator/api/examiners.py` → `get_examiners()`, `create_assignment()`
- **Description:** Examiner list returned all examiners globally including soft-deleted ones. Assignment creation didn't validate session ownership.
- **Impact:** Coordinators could assign examiners from other departments to their sessions, or view examiner details across departments.
- **Fix Applied:** Scoped examiner list by `coordinator_department`, added `is_deleted=False` filter, added session ownership validation for assignments.

---

### VULN-008: `is_staff` Used Instead of `is_superuser` for Admin Bypass
- **ID:** VULN-008
- **Severity:** MEDIUM
- **Category:** Privilege Escalation (CWE-269)
- **Location:** `examiner/views/api.py` → `get_session_students()`, `start_marking()`, `sync_offline_data()`
- **Description:** Three examiner API endpoints used `request.user.is_staff` to bypass assignment checks. In Django, `is_staff` only means "can access admin site" — it does not imply superuser privileges. Admin-level coordinators have `is_staff=True`, so they could bypass assignment validation intended only for superusers.
- **Impact:** Admin coordinators could access any examiner session data regardless of assignment.
- **Fix Applied:** Changed `is_staff` to `is_superuser` in all three locations.

---

### VULN-009: Checklist Item Not Validated Against Station
- **ID:** VULN-009
- **Severity:** MEDIUM
- **Category:** IDOR / Data Integrity (CWE-639)
- **Location:** `examiner/views/api.py` → `mark_item()`, `batch_mark_items()`
- **Description:** When scoring a checklist item, the `checklist_item_id` was accepted without validating it belongs to the station being scored. An examiner could submit scores for checklist items from a completely different station.
- **Attack Scenario:** Examiner sends `POST /api/mark/123/` with `checklist_item_id` from station B while scoring station A → the score is recorded under station A with an unrelated checklist item.
- **Impact:** Data integrity compromise; incorrect scoring data.
- **Fix Applied:** In `mark_item()`, changed to `get_object_or_404(ChecklistItem, pk=checklist_item_id, station=score.station)`. In `batch_mark_items()`, added bulk validation that all submitted item IDs belong to the station.

```python
# BEFORE (vulnerable)
checklist_item = get_object_or_404(ChecklistItem, pk=checklist_item_id)

# AFTER (fixed)
checklist_item = get_object_or_404(ChecklistItem, pk=checklist_item_id, station=score.station)
```

---

### VULN-010: 403 Response Leaks Resource Existence
- **ID:** VULN-010
- **Severity:** MEDIUM
- **Category:** Information Disclosure (CWE-200)
- **Location:** `examiner/views/api.py` → `get_session_students()`
- **Description:** When an examiner requested students for a session they were not assigned to, the API returned HTTP 403. This differs from what a non-existent session would return (404), allowing attackers to enumerate valid session IDs.
- **Impact:** Session ID enumeration.
- **Fix Applied:** Changed 403 to 404 for unauthorized access.

---

### VULN-011: `ALLOWED_HOSTS` Defaults to `['*']`
- **ID:** VULN-011
- **Severity:** MEDIUM
- **Category:** Security Misconfiguration (CWE-16)
- **Location:** `osce_project/settings/base.py`
- **Description:** `ALLOWED_HOSTS` defaulted to `['*']` if not set in the environment, accepting requests from any hostname.
- **Impact:** Host header injection; potential for cache poisoning, password reset poisoning.
- **Fix Applied:** Changed default to `['localhost', '127.0.0.1']`.

---

### VULN-012: `SECRET_KEY` Has Insecure Default
- **ID:** VULN-012
- **Severity:** MEDIUM
- **Category:** Cryptographic Failure (CWE-798)
- **Location:** `osce_project/settings/base.py`
- **Description:** `SECRET_KEY` had a hardcoded default value `'django-insecure-change-me-in-production'` used when the env var was missing. If deployed without setting the env var, sessions and CSRF tokens would use this predictable key.
- **Impact:** Session forgery, CSRF bypass, cookie tampering.
- **Fix Applied:** Removed default entirely. The setting will now raise `ImproperlyConfigured` if `SECRET_KEY` is not in the environment. The `.env.example` file already documents the required value.

---

### VULN-013: Reports/Exports — Cross-Department Data Exfiltration
- **ID:** VULN-013
- **Severity:** MEDIUM
- **Category:** Broken Access Control (CWE-862)
- **Location:** `creator/api/reports.py` — all 5 endpoints
- **Description:** Session summary reports and CSV/XLSX export endpoints accepted any session ID without department validation. A coordinator could export full student data, scores, and examiner details from other departments.
- **Impact:** Bulk data exfiltration across department boundaries.
- **Fix Applied:** Created `_scoped_session()` helper and applied to all 5 report/export endpoints.

---

### VULN-014 (LOW — Accepted): `@csrf_exempt` on Examiner Sync Endpoints
- **ID:** VULN-014
- **Severity:** LOW
- **Category:** CSRF (CWE-352)
- **Location:** `examiner/views/api.py` — 4 endpoints
- **Description:** Four examiner API endpoints use `@csrf_exempt` to support offline PWA sync. These endpoints are protected by `@login_required` and examiner assignment checks.
- **Status:** Accepted risk. CSRF exemption is required for the offline-first tablet PWA architecture. Mitigated by: session auth, assignment validation, and SameSite=Lax cookies.

---

### VULN-015 (LOW — Accepted): CSP Allows `unsafe-inline`
- **ID:** VULN-015
- **Severity:** LOW
- **Category:** XSS Mitigation Gap (CWE-79)
- **Location:** `core/middleware.py` → CSP header
- **Description:** Content Security Policy includes `'unsafe-inline'` for both `script-src` and `style-src`, reducing XSS defense effectiveness.
- **Status:** Accepted risk. Removing `unsafe-inline` requires refactoring all inline event handlers and styles to external files — planned for a future release.

---

### VULN-016 (LOW — Accepted): Default Password for Bulk-Created Examiners
- **ID:** VULN-016
- **Severity:** LOW
- **Category:** Weak Credentials (CWE-521)
- **Location:** Examiner bulk upload flow
- **Description:** Bulk-created examiners receive a default password. A `force_change_password` flag is set, but if the examiner never logs in, the weak password persists.
- **Status:** Accepted risk. Mitigated by force-change-password enforcement on first login and network access controls during exam sessions.

---

## 3. Security Checklist

### Authentication & Session Management
- [x] Login form uses `authenticate()` + `login()`
- [x] Soft-deleted users blocked at login *(VULN-001 fix)*
- [x] Rate limiting: 5 failed attempts → 15-min lockout (django-axes)
- [x] SESSION_COOKIE_HTTPONLY = True
- [x] SESSION_COOKIE_SECURE = True (production)
- [x] SESSION_COOKIE_SAMESITE = 'Lax'
- [x] SESSION_COOKIE_AGE = 43200 (12 hours)
- [x] Force password change on first login
- [x] Generic error messages on login failure

### Authorization & Access Control
- [x] `@login_required` on all 45+ creator/examiner endpoints
- [x] `scope_queryset()` applied to all v1 creator API endpoints *(VULN-002 fix)*
- [x] `DepartmentScopedMixin` used in v2 DRF ViewSets
- [x] Row-Level Security (RLS) at database level — 40+ policies, 10 helper functions
- [x] `role_required()` decorator for role gating
- [x] Examiner assignment validation before marking
- [x] Session↔Student cross-validation in StationScore creation *(VULN-004 fix)*
- [x] Checklist item↔station validation in marking *(VULN-009 fix)*
- [x] `is_superuser` (not `is_staff`) for admin bypass *(VULN-008 fix)*
- [x] 404 (not 403) for unauthorized resource access *(VULN-010 fix)*

### SQL Injection Prevention
- [x] Django ORM used exclusively — no `.raw()`, `.extra()`, or string interpolation
- [x] RLS session variables set from server-side middleware only
- [x] All search queries use hardcoded field names
- [x] Parameterized queries in all ORM calls

### Input Validation
- [x] Django Forms for all user-facing inputs
- [x] File upload: 5MB max, .xlsx/.xls whitelist
- [x] Content-Disposition sanitization (`_safe_filename()`)
- [x] Open redirects validated with `url_has_allowed_host_and_scheme()` *(VULN-005 fix)*
- [x] JSON body parsing with explicit error handling

### Configuration Security
- [x] SECRET_KEY required from environment — no default *(VULN-012 fix)*
- [x] ALLOWED_HOSTS defaults to `['localhost', '127.0.0.1']` *(VULN-011 fix)*
- [x] DEBUG = False in production
- [x] SECURE_SSL_REDIRECT = True in production
- [x] SECURE_HSTS_SECONDS = 31536000 in production
- [x] `.env` in `.gitignore`
- [x] SECRET_ADMIN_URL for admin panel

### Output & Error Handling
- [x] Django template auto-escaping enabled
- [x] CSP headers configured
- [x] Custom error handlers (400, 403, 404, 500) with no sensitive data
- [x] X-Frame-Options: SAMEORIGIN
- [x] X-Content-Type-Options: nosniff
- [x] Referrer-Policy: strict-origin-when-cross-origin

### Audit & Monitoring
- [x] `log_action()` for login/logout, score submissions, session state changes
- [x] Audit logs include: user, timestamp, action type, entity
- [x] Search engine blocking (robots.txt, noindex meta, 404 on sitemap.xml)

---

## 4. Recommended Additional Measures

### High Priority
1. **Remove `unsafe-inline` from CSP** — Refactor inline scripts/styles to external files, then tighten CSP to eliminate XSS attack surface
2. **API rate limiting** — Add `django-ratelimit` to all API endpoints (currently only login is rate-limited)
3. **Media file authentication** — In production, configure nginx/reverse proxy to require authentication for `/media/` paths (Django's `static()` is a no-op when `DEBUG=False`, so media must be served by the web server — ensure it requires auth)
4. **Automated security scanning** — Integrate Bandit (Python SAST) and OWASP ZAP into CI/CD pipeline

### Medium Priority
5. **Two-factor authentication (2FA)** — Add TOTP-based 2FA for admin and coordinator accounts
6. **Password reset flow** — Implement token-based email password reset
7. **Database encryption at rest** — Enable PostgreSQL TDE or Azure database encryption
8. **Rotate default passwords** — Add a management command to identify accounts still using default passwords

### Low Priority
9. **HSTS preload** — Submit domain to HSTS preload list after verifying all subdomains support HTTPS
10. **Audit log retention policy** — Define automated cleanup for logs older than N months
11. **IP allowlisting** — Consider restricting creator interface access to institutional IP ranges
12. **Virus scanning** — Scan uploaded XLSX files for embedded macros/malware

---

## 5. Files Modified in This Audit

| File | Changes |
|------|---------|
| `core/views.py` | Blocked soft-deleted user login |
| `creator/api/courses.py` | Added department scoping to course/ILO/library queries |
| `creator/api/examiners.py` | Added department scoping + soft-delete filter + session ownership |
| `creator/api/exams.py` | Added department scoping to all 8 exam endpoints |
| `creator/api/sessions.py` | Added `_scoped_session()` helper, scoped all 10 session endpoints |
| `creator/api/stations.py` | Added department scoping to station delete |
| `creator/api/students.py` | Added `_scoped_session()` and `_scoped_student()` helpers, scoped all 7 endpoints |
| `creator/api/stats.py` | Scoped all 9 stat counters by department |
| `creator/api/paths.py` | Added `_scoped_session()` and `_scoped_path()` helpers, scoped all 9 endpoints |
| `creator/api/library.py` | Added department scoping to library CRUD + ILO ownership validation |
| `creator/api/reports.py` | Added `_scoped_session()` helper, scoped all 5 report/export endpoints |
| `creator/views/examiners.py` | Added department scoping to list/detail/edit + fixed open redirect |
| `creator/views/courses.py` | Fixed 2 open redirects |
| `core/api/views.py` | Added session↔student cross-validation in StationScore creation |
| `examiner/views/api.py` | Fixed is_staff→is_superuser, 403→404, checklist item station validation |
| `osce_project/settings/base.py` | Removed SECRET_KEY default, tightened ALLOWED_HOSTS |

---

**Audited by:** GitHub Copilot (AI Assistant)  
**Methodology:** Full codebase scan with 3 specialized sub-agents (SQL injection, IDOR/data leakage, auth/settings) + manual review and fix implementation  
**Total Vulnerabilities:** 16 found (13 fixed, 3 accepted low-risk)
