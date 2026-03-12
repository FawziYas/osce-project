# Security Levels Across the OSCE App

This document summarizes the security levels and controls that are already implemented across the OSCE application. It is based on the current codebase and the existing security audit reports.

## 1. Environment and Deployment Security

- `SECRET_KEY` is read from environment variables in production.
- `DEBUG = False` is enforced in production settings.
- `ALLOWED_HOSTS` is environment-driven in production.
- Production enables HTTPS hardening:
  - `CSRF_COOKIE_SECURE = True`
  - `CSRF_COOKIE_HTTPONLY = True`
  - `SESSION_COOKIE_SECURE = True`
  - `SECURE_SSL_REDIRECT = True` by default
  - `SECURE_HSTS_SECONDS = 31536000`
  - `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
  - `SECURE_HSTS_PRELOAD = True`
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
  - `X_FRAME_OPTIONS = 'SAMEORIGIN'`

## 2. Authentication Security

- The app uses a custom Django user model: `core.Examiner`.
- Authentication is session-based for both the web app and DRF APIs.
- Login is protected by `django-axes` rate limiting.
- Failed login attempts are limited by username plus IP address.
- Login attempts reset on success.
- Open redirect protection is implemented in `login_view()` using allowed-host validation on the `next` parameter.

## 3. Password Security

- Django password validators are enabled in base settings.
- Production uses stricter password length requirements.
- New non-superuser accounts are provisioned with a default password, but they are forced to change it on first use.
- `ForcePasswordChangeForm` blocks weak replacements and blocks reusing the default password.
- `UserPasswordChangeForm` requires the current password and enforces strength rules.
- Password changes keep the session alive through `update_session_auth_hash()`.

## 4. Session Security

- Session cookies are `HttpOnly`.
- Session cookies use `SameSite=Lax`.
- Session expiry slides on activity with `SESSION_SAVE_EVERY_REQUEST = True`.
- `SessionTimeoutMiddleware` applies shorter idle timeout for creator users and longer timeout for examiners.
- The app enforces a single active session per user through `UserSession` checks at login.
- Logout cleans up tracked user sessions.

## 5. Admin Security Layer

- The default `/admin/` path is blocked with `404`.
- The real admin path is moved behind `SECRET_ADMIN_URL`.
- Admin access requires a second session gate: `request.session['admin_unlocked']`.
- Admin unlock is only available through `admin_gateway_view()`.
- The gateway requires:
  - authenticated user
  - staff user
  - correct secret token
- The admin token is only injected into template context for authenticated staff users.

## 6. Role-Based Access Control

- `RoleBasedAccessMiddleware` separates creator and examiner interfaces.
- Examiners are blocked from `/creator/` and `/api/creator/`.
- Superusers, admins, and coordinators are redirected away from examiner-only functional pages.
- DRF permission classes provide explicit role gates:
  - `IsSuperuser`
  - `IsAdmin`
  - `IsCoordinator`
  - `IsCoordinatorHead`
  - `IsExaminer`
  - composite permission classes for mixed access rules
- Some permissions are auto-synced by signals, such as `can_view_student_list` for admin and coordinator-head roles.

## 7. Data Scope Security

- `DepartmentScopedMixin` restricts coordinators to their own department data.
- `ExaminerAssignmentMixin` restricts examiners to stations assigned to them.
- Unauthorized object access is designed to return `404` instead of confirming object existence.
- `RLSSessionMiddleware` pushes user context into PostgreSQL session variables for Row-Level Security policies when PostgreSQL is used.
- RLS context includes:
  - current user ID
  - resolved role
  - department ID
  - assigned station IDs for examiners

## 8. API and Request Protection

- Django CSRF middleware is enabled globally.
- Examiner UI requests include CSRF tokens for protected operations.
- Scoring endpoints that use browser-submitted CSRF tokens are protected without `@csrf_exempt`.
- A few offline-first endpoints remain `@csrf_exempt`, but they use compensating controls such as assignment checks and ownership checks.
- JSON request parsing is hardened with `_parse_json_body()` to avoid server errors on malformed input.
- Default DRF permission is `IsAuthenticated`.

## 9. Examiner Workflow Security

- Examiner APIs verify station or session assignment before returning data or accepting writes.
- `start_marking()` verifies that the examiner is assigned to the target session and station.
- `start_marking()` also blocks marking when the session is not active.
- `mark_item()`, `submit_score()`, `undo_submit()`, and batch operations verify score ownership before updates.
- Offline sync checks both assignment scope and record ownership before accepting updates.
- Dry exam verification uses server-side session authorization rather than trusting URL parameters alone.
- Dry authorization records include user ID, student ID, assignment ID, and expiry timestamp.

## 10. Secure Headers and Browser Security

- `ContentSecurityPolicyMiddleware` sets a Content Security Policy.
- `ReferrerPolicyMiddleware` sets `strict-origin-when-cross-origin`.
- `PermissionsPolicyMiddleware` disables browser features not needed by the app:
  - camera
  - microphone
  - geolocation
  - payment
- Production also enables browser XSS filtering and content-type sniffing protection.

## 11. Input and File Validation

- Django forms are used for password changes and other validated workflows.
- Audit reports confirm validation coverage for creator-side forms and file upload flows.
- File uploads are restricted by type and size in the creator flows.
- The app relies on Django ORM access patterns rather than raw SQL, reducing SQL injection risk.

## 12. Audit, Monitoring, and Detection

- Successful logins, failed logins, and logouts are logged.
- Unauthorized `401`, `403`, and `404` responses are logged by middleware as possible access attempts.
- Business actions such as score submission, correction, sync, and admin unlock are audit logged.
- Hierarchy model create, update, and delete events are recorded through signals.
- Separate audit and auth loggers write to log files.
- Production uses rotating log files.
- Optional Sentry integration is available with PII disabled by default.

## 13. Error Handling and Information Disclosure Control

- The app uses custom error handlers for `400`, `403`, `404`, and `500` responses.
- Invalid JSON bodies return controlled `400` responses instead of unhandled exceptions.
- Admin and unauthorized-path failures often return `404` to reduce information leakage.
- Static-file 404 noise is ignored in unauthorized-access logging to keep logs usable.

## Security Model Summary

The app uses defense in depth rather than a single control. The implemented levels are:

1. Deployment and transport hardening
2. Login protection and password policy
3. Forced password rotation for provisioned users
4. Session timeout and single-session enforcement
5. Hidden and gated admin access
6. Role-based access control
7. Department and station assignment scoping
8. API request validation and CSRF protection
9. Examiner workflow ownership and assignment checks
10. Secure headers and browser restrictions
11. Input validation and ORM-based database safety
12. Audit logging and unauthorized access monitoring

## Main Code References

- `osce_project/settings/base.py`
- `osce_project/settings/production.py`
- `osce_project/urls.py`
- `core/middleware.py`
- `core/views.py`
- `core/signals.py`
- `core/context_processors.py`
- `core/api/permissions.py`
- `core/api/mixins.py`
- `examiner/views/api.py`
- `SECURITY_AUDIT_REPORT.md`
- `SECURITY_PERFORMANCE_AUDIT.md`