deeply thinking ask me anything you want before action
You are a senior application security engineer specializing in 
Django + PostgreSQL security audits.

Perform a comprehensive SQL injection and data leakage audit on 
the provided Django application code. This app uses:
  - Django REST Framework (DRF)
  - PostgreSQL with Row-Level Security (RLS)
  - Session variables for role context
    (app.current_role, app.department_id, 
     app.current_user_id, app.station_ids)
  - JWT authentication
  - Role hierarchy:
    Superuser → Admin → Coordinator (Head/Organizer/RTA) → Examiner

═══════════════════════════════════════════════════════════════
SECTION 1 — SQL INJECTION AUDIT
═══════════════════════════════════════════════════════════════

## 1.1 Raw SQL Execution Points
Scan ALL files for raw SQL usage:
  - connection.cursor().execute(...)
  - cursor.executemany(...)
  - Manager.raw(...)
  - Model.objects.raw(...)
  - extra(where=[...])
  - RawSQL(...)
  - Func(...) with raw SQL strings

For each occurrence found:
  - File name + line number
  - The exact SQL string
  - Are user-supplied values interpolated with % or .format() 
    or f-strings? → CRITICAL INJECTION RISK
  - Are parameterized placeholders (%s) used correctly?
  - Verdict: SAFE / VULNERABLE / REVIEW NEEDED

## 1.2 ORM Usage That Can Lead to Injection
Check for unsafe ORM patterns:
  - .extra(select={...}) with unsanitized input
  - .filter(**user_supplied_dict) without field whitelist
    (allows arbitrary field lookups e.g. password__contains)
  - order_by(user_supplied_string) without validation
    (allows column enumeration)
  - annotate() or aggregate() with raw expressions
    built from user input
  - Q() objects constructed from unsanitized user input
  - .values(user_supplied_field_name)

For each occurrence:
  - File + line number
  - Input source (request.GET / request.POST / URL param)
  - Is the input validated/whitelisted before use?
  - Verdict: SAFE / VULNERABLE / REVIEW NEEDED

## 1.3 Session Variable Injection
This app sets PostgreSQL session variables via:
  set_config('app.current_role', role, True)
  set_config('app.department_id', dept_id, True)

Check:
  - Are session variable VALUES ever derived from 
    user-supplied input (request body, headers, URL)?
    → CRITICAL: attacker could set their own role
  - Are values always sourced from server-side 
    user profile only?
  - Is set_config called with parameterized values 
    or string concatenation?
  - Could an attacker inject a role string like:
    "SUPERUSER'; DROP TABLE exam;--"
    into the session variable pipeline?
  - Verdict per variable: SAFE / VULNERABLE / REVIEW NEEDED

## 1.4 PostgreSQL RLS Policy Injection
Review all RLS policy SQL for:
  - Any policy that concatenates user input into SQL
  - Any policy using EXECUTE or dynamic SQL
  - Any policy that trusts current_setting() values 
    without type casting (e.g. missing ::uuid cast 
    could allow type confusion attacks)
  - Verify FORCE ROW LEVEL SECURITY is set on all tables
  - Verify no table has BYPASSRLS granted to the app DB user

## 1.5 URL Parameter Injection
Check all URL parameters used in querysets:
  - /api/exams/:examId/ — is examId validated as UUID 
    before hitting the ORM?
  - /api/departments/:deptId/ — same
  - Any endpoint accepting list parameters 
    (e.g. ?ids=1,2,3) — are these split and validated?
  - Any endpoint with search/filter params 
    (e.g. ?name=...) — are these passed raw to ORM?

## 1.6 Serializer & Form Input Injection
Check DRF serializers for:
  - Fields that pass raw user input into ORM queries
  - SerializerMethodField that executes queries 
    using unvalidated request data
  - Writable nested serializers that could 
    manipulate FK relationships across departments

═══════════════════════════════════════════════════════════════
SECTION 2 — DATA LEAKAGE AUDIT
═══════════════════════════════════════════════════════════════

## 2.1 Cross-Department Data Leakage
This is the most critical risk in this app.
A Coordinator from Dept A must NEVER receive 
data belonging to Dept B.

Check every ViewSet and APIView for:
  - Does get_queryset() filter by department?
  - Does get_object() verify department ownership?
  - Are nested serializers scoped to the same department?
  - Can a Coordinator manipulate a FK field in a 
    POST/PUT request to point to another dept's object?
    (e.g. POST /exams/ with course_id from Dept B)
  - Are bulk operations (bulk_create, bulk_update) 
    scoped per department?

For each ViewSet:
  - List the queryset scope applied
  - Identify any missing department filter
  - Verdict: SAFE / LEAKS DATA / REVIEW NEEDED

## 2.2 Examiner Data Leakage
Examiner must ONLY access their assigned stations.

Check:
  - Every endpoint Examiner can reach — is it filtered 
    by ExaminerAssignment?
  - Can Examiner access /api/stations/ list and see 
    all stations (not just assigned)?
  - Can Examiner retrieve another Examiner's scores?
  - Can Examiner access /api/paths/ or /api/sessions/ 
    or /api/exams/ at all?
  - Can Examiner POST a score to a station they are 
    not assigned to by supplying a different station_id?

## 2.3 API Response Leakage
Check all DRF serializers for:
  - Fields that expose sensitive data to wrong roles
    (e.g. ExamSerializer returning department data 
    to Examiner)
  - Serializers that return ALL fields by default 
    (Meta: fields = '__all__') — flag every occurrence
  - Nested serializers that expose parent objects 
    a role should not see
  - Error messages that reveal existence of resources
    (e.g. "Exam not found" vs "Permission denied" — 
    the former confirms the exam exists)
  - Stack traces or DEBUG info leaking in responses
  - Internal IDs, file paths, or server info in 
    error responses

## 2.4 URL Enumeration & IDOR
(Insecure Direct Object Reference)

Check:
  - Can a Coordinator from Dept A access 
    /api/exams/<valid-dept-B-uuid>/ and get a 200?
    → Should return 404, never 403
  - Can an Examiner access 
    /api/stations/<unassigned-uuid>/ and get a 200?
    → Should return 404
  - Are UUIDs used for all resource IDs?
    (sequential integers allow easy enumeration)
  - Are there any endpoints that return existence 
    information in 403 vs 404 differentiation?
  - Can an attacker brute-force UUIDs via list endpoints?

## 2.5 Filter & Search Parameter Leakage
Check all endpoints that accept filter/search params:
  - ?department=<uuid> — can a Coordinator override 
    their own department filter?
  - ?exam=<uuid> — can this leak cross-dept exam data?
  - ?search=<string> — does search query scope 
    respect RLS or does it search globally?
  - Ordering params — can order_by leak field 
    existence via timing attacks?

## 2.6 Audit Log Leakage
Check the AuditLog system:
  - Can a Coordinator query audit logs from 
    another department?
  - Does the log export endpoint enforce 
    department scoping server-side?
  - Are sensitive field values (passwords, tokens) 
    ever captured in old_value / new_value JSONField?
  - Are IP addresses and user agents stored securely?

## 2.7 JWT & Session Leakage
Check authentication layer for:
  - JWT payload — does it expose role, department_id, 
    or other sensitive claims unnecessarily?
  - Is the JWT secret strong and stored in environment 
    variables (never hardcoded)?
  - Token expiry — are access tokens short-lived?
  - Are refresh tokens rotated after use?
  - Is the role in the JWT trusted directly by views 
    without re-checking DB?
    → RISK: attacker could forge JWT claims if secret 
    is weak or if JWT is not re-validated against DB

## 2.8 File & Media Leakage
If the app serves uploaded files:
  - Are file URLs guessable (sequential or predictable)?
  - Are files served through Django with permission 
    checks or directly via web server (bypassing auth)?
  - Can an unauthenticated user download a file 
    by guessing the URL?

## 2.9 Django Settings Leakage
Check settings.py for:
  - DEBUG = True in production → leaks full stack traces
  - SECRET_KEY hardcoded (not from environment variable)
  - DATABASE_URL or credentials hardcoded
  - ALLOWED_HOSTS = ['*'] → open to host header attacks
  - CORS_ALLOW_ALL_ORIGINS = True → open to cross-origin 
    data theft
  - Sensitive keys committed to version control (.env 
    checked into git)

═══════════════════════════════════════════════════════════════
SECTION 3 — MIDDLEWARE SECURITY AUDIT
═══════════════════════════════════════════════════════════════

Review the full MIDDLEWARE stack in settings.py:

Check ordering:
  - SecurityMiddleware must be FIRST
  - SessionMiddleware before AuthenticationMiddleware
  - SetDBSessionMiddleware must run AFTER 
    AuthenticationMiddleware (needs request.user)
  - Cache middleware must not wrap SetDBSessionMiddleware
    (would serve cached RLS-bypassed responses)

Check for missing security middleware:
  - django.middleware.security.SecurityMiddleware
  - django.middleware.clickjacking.XFrameOptionsMiddleware
  - django.middleware.csrf.CsrfViewMiddleware
    (if using session auth alongside JWT)

Check SetDBSessionMiddleware specifically:
  - Does it handle AnonymousUser safely?
  - Does it handle exceptions without crashing the request?
  - Are session variables ALWAYS set (even to empty string)
    to prevent previous request values leaking?
  - Is it impossible for a client to influence what 
    values get set into session variables?

═══════════════════════════════════════════════════════════════
SECTION 4 — OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

## Executive Summary
- Total vulnerabilities found
- Breakdown by severity: CRITICAL / HIGH / MEDIUM / LOW / INFO
- Top 3 most urgent issues to fix immediately

## Vulnerability Report
For each issue found provide:

  ID:             VULN-001
  Title:          Brief descriptive title
  Severity:       CRITICAL / HIGH / MEDIUM / LOW
  Category:       SQL Injection / Data Leakage / IDOR / 
                  Config / Auth
  Location:       file_name.py line X
  Description:    What the vulnerability is
  Attack Scenario:How an attacker would exploit it
                  (step by step)
  Impact:         What data or access they would gain
  Fix:            Exact code change required
  Verification:   How to test that the fix works

## Clean Code Examples
For every CRITICAL and HIGH finding, provide:
  - The vulnerable code (before)
  - The secure code (after)
  - Explanation of what changed and why

## Security Checklist
At the end, provide a checklist of all items audited:
  ✅ Safe
  ❌ Vulnerable
  ⚠️  Needs Review

## Recommended Additional Measures
After fixing found issues, recommend:
  - Django security settings to add/harden
  - Additional DRF permission classes needed
  - PostgreSQL-level hardening steps
  - Rate limiting recommendations
  - Penetration testing steps to verify fixes

═══════════════════════════════════════════════════════════════
SECTION 5 — FILES TO ANALYZE
═══════════════════════════════════════════════════════════════

Provide ALL of the following for a complete audit:

  1. settings.py
  2. urls.py (root + app-level)
  3. middleware.py (or middleware/ folder)
  4. models.py (all models)
  5. views.py / viewsets.py (all)
  6. serializers.py (all)
  7. permissions.py (custom DRF permissions)
  8. migrations/000X_rls_policies.py
  9. Any raw SQL files or management commands
  10. requirements.txt