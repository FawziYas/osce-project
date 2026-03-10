# Production Deployment Checklist — Azure

**Project:** Django OSCE Exam System
**Platform:** Microsoft Azure (covered by $100/mo university credit)
**Last Updated:** March 4, 2026

---

## ⚡ Key Production Changes (Mandatory)

| # | Change | Status | Notes |
|---|--------|--------|-------|
| 1 | **SQLite → PostgreSQL** | ⬜ TODO | `dj-database-url` configured in `production.py` — need Azure PostgreSQL Flexible Server |
| 2 | **`DEBUG = False` + `ALLOWED_HOSTS`** | ✅ DONE | Configured in `production.py` via env vars |
| 3 | **WhiteNoise for static files** | ✅ DONE | Middleware added in `base.py`, `CompressedManifestStaticFilesStorage` in `production.py` |
| 4 | **Gunicorn as WSGI server** | ✅ DONE | `gunicorn.conf.py` + `Procfile` created (gthread, auto workers, max-requests) |
| 5 | **`SECRET_KEY` from environment** | ✅ DONE | `production.py` reads from `SECRET_KEY` env var, `.env.example` documents generation |
| 6 | **Row-Level Security (RLS)** | ✅ DONE | Migration `0027_rls_policies.py` — 10 helper functions, 40+ policies over 10 tables. Auto-skips on SQLite, activates on PostgreSQL. `RLSSessionMiddleware` sets session vars per request. See `RLS_DESIGN.md` |
| 7 | **RBAC system** | ✅ DONE | `core/utils/permissions.py` — role-based decorators on all 140+ endpoints (superuser > admin > coordinator > examiner). Coordinator department scoping enforced |
| 8 | **Audit Logging System** | ✅ DONE | 37 action types, `AuditLogService` with old/new value JSON diff, department scoping, role-scoped admin with streaming CSV/JSON export, `AuditLogArchive` model + `archive_old_logs` management command |
| 9 | **Celery async audit writes** | ✅ DONE | `osce_project/celery.py` + `core/tasks.py`. Falls back to synchronous writes when `CELERY_BROKER_URL` is not set |
| 10 | **Unauthorized access logging** | ✅ DONE | `UnauthorizedAccessMiddleware` auto-logs 401/403/404 responses to AuditLog |

---

## 🏗 Azure Architecture

```
                    ┌──────────────────┐
                    │  Azure Front Door │  ← CDN + DDoS + WAF + SSL (optional)
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────────┐
                    │  Azure App Service    │  ← B2 plan, autoscale 1-3
                    │  (Gunicorn workers)   │
                    └──┬───┬───┬───┬───────┘
                       │   │   │   │
              ┌────────┘   │   │   └────────┐
              ▼            ▼   ▼            ▼
        ┌──────────┐ ┌──────────┐     ┌──────────┐
        │PostgreSQL│ │ Azure    │     │WhiteNoise│
        │ Flexible │ │ Redis    │     │ Static   │
        │ Server   │ │ Cache C0 │     │ Files    │
        │ + RLS    │ └────┬─────┘     └──────────┘
        │ policies │      │
        └──────────┘      ▼
                    ┌──────────────┐
                    │Celery Worker │  ← WebJob or same App Service
                    │(audit writes)│     (async audit log queue)
                    └──────────────┘
```

### Estimated Monthly Cost

| Component | Azure Service | Monthly Cost |
|-----------|--------------|-------------|
| Web Server | App Service B2 (2 vCPU, 3.5GB RAM) | ~$54 |
| PostgreSQL | Flexible Server Burstable B1ms | ~$25 |
| Connection Pooling | Built-in PgBouncer (Flexible Server) | $0 (included) |
| Redis Cache | Azure Cache for Redis Basic C0 | ~$13 |
| SSL | App Service Managed Certificate | $0 |
| Error Monitoring | Sentry (free tier) | $0 |
| Uptime Monitoring | Azure Monitor (free tier) | $0 |
| Celery Worker | App Service WebJob or AlwaysOn | ~$0 (shares App Service) |
| **Total** | | **~$92/month** |
| **University credit** | | **$100/month** |
| **Out of pocket** | | **$0** |

### Expected Performance at 1000 Concurrent Examiners

| Metric | Without Optimization | With Azure Full Setup |
|--------|---------------------|-----------------------|
| Score submission | 800ms | **< 150ms** |
| Exam detail page | 500ms | **< 100ms** (cached) |
| Login | 300ms | **< 200ms** |
| Report generation | 5s | **< 2s** |
| Max concurrent users | ~100 (then crash) | **1000+ stable** |
| DB connections used | 1000 (exhausted) | **25 via PgBouncer** |
| Autoscale | Not available | **1-3 instances auto** |

---

## 🔴 P0 — CRITICAL (Do These First)

### 1. Azure PostgreSQL + PgBouncer

Without this, 100+ concurrent examiners = database crash (SQLite locks on writes).

- [ ] **Create Azure PostgreSQL Flexible Server** (Burstable B1ms)
  - [ ] Azure Portal → Create Resource → Azure Database for PostgreSQL Flexible Server
  - [ ] SKU: Burstable B1ms (1 vCPU, 2GB RAM) — enough for 1000 users
  - [ ] Create database: `osce_production`
  - [ ] Create least-privilege app user (**must NOT be a superuser** — otherwise RLS policies are bypassed!):
    ```sql
    CREATE USER osce_app WITH PASSWORD 'strong_16+_char_password';
    GRANT CONNECT ON DATABASE osce_production TO osce_app;
    GRANT USAGE ON SCHEMA public TO osce_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO osce_app;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO osce_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO osce_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO osce_app;
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO osce_app;
    ```
    > **Critical:** The app user must be a regular (non-superuser) PostgreSQL role.
    > PostgreSQL superusers bypass ALL RLS policies. See `RLS_DESIGN.md` for details.

- [ ] **Enable PgBouncer** (built-in, free)
  - [ ] Azure Portal → Your PostgreSQL server → Server Parameters
  - [ ] Set `pgbouncer.enabled` = `true`
  - [ ] Set `pgbouncer.default_pool_size` = `25`
  - [ ] Connect via port 6432 (PgBouncer) instead of 5432

- [ ] **Set `DATABASE_URL` in App Service**
  ```
  DATABASE_URL=postgresql://osce_app:PASSWORD@yourserver.postgres.database.azure.com:6432/osce_production
  ```

- [ ] **Run migrations on production DB**
  ```bash
  python manage.py migrate
  python manage.py createsuperuser
  ```
  > Migration `0027_rls_policies.py` will automatically create all RLS
  > helper functions, enable/force RLS on 10 tables, and create 40+ policies.
  > Migration `0029` will create the enhanced AuditLog schema + AuditLogArchive table.

### 2. Azure App Service Deployment

- [ ] **Create Azure App Service** (Linux, Python 3.13, B2 plan)
  - [ ] Azure Portal → Create Resource → Web App
  - [ ] Runtime: Python 3.13
  - [ ] Plan: B2 (2 vCPU, 3.5GB RAM) — handles 1000 concurrent users
  - [ ] Region: Same as PostgreSQL server (minimize latency)

- [ ] **Connect GitHub repo for auto-deployment**
  - [ ] App Service → Deployment Center → GitHub → select repo + branch
  - [ ] Or use Azure CLI:
    ```bash
    az webapp up --name osce-app --resource-group osce-rg --runtime "PYTHON:3.13"
    ```

- [ ] **Set startup command**
  ```
  gunicorn osce_project.wsgi:application --config gunicorn.conf.py
  ```

- [ ] **Configure environment variables** (App Service → Configuration → Application Settings)
  ```
  DJANGO_ENV=production
  SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
  DATABASE_URL=postgresql://...
  ALLOWED_HOSTS=osce-app.azurewebsites.net,yourdomain.com
  DJANGO_SETTINGS_MODULE=osce_project.settings
  CELERY_BROKER_URL=rediss://:ACCESS_KEY@yourredis.redis.cache.windows.net:6380/0
  ```

- [ ] **Run collectstatic**
  ```bash
  python manage.py collectstatic --no-input
  ```

- [ ] **Enable autoscale** (1-3 instances based on CPU > 70%)
  - [ ] App Service → Scale out → Custom autoscale
  - [ ] Min: 1, Max: 3, Scale up when CPU > 70%

### 3. SSL/HTTPS

Azure App Service provides free managed SSL for `*.azurewebsites.net` domains.

- [ ] **For custom domain:**
  - [ ] App Service → Custom domains → Add domain
  - [ ] App Service → TLS/SSL settings → Create App Service Managed Certificate (free)
  - [ ] Verify DNS is configured (CNAME or A record)

- [x] **Django SSL settings** — already in `production.py`
  - HSTS, secure cookies, SSL redirect all configured

---

## 🟡 P1 — HIGH IMPACT (Before Exam Day)

### 4. Azure Redis Cache

- [x] **Django Redis packages installed** — `django-redis`, `redis` in `requirements.txt`
- [x] **Redis cache + session backend configured** — `production.py` reads `REDIS_URL`, falls back to LocMemCache
- [ ] **Create Azure Cache for Redis** (Basic C0, 250MB, ~$13/mo)
  - [ ] Azure Portal → Create Resource → Azure Cache for Redis
  - [ ] SKU: Basic C0
  - [ ] Copy connection string from Access Keys blade
- [ ] **Set `REDIS_URL` in App Service**
  ```
  REDIS_URL=rediss://:ACCESS_KEY@yourredis.redis.cache.windows.net:6380/1
  ```
  (Note: `rediss://` with double-s for SSL)

- [ ] **Cache expensive queries in views** (exam detail, course list, session paths)

  | Data | Cache Duration | Why |
  |------|---------------|-----|
  | Exam details (stations, ILOs) | 10 min | Doesn't change during exam |
  | Course & ILO list | 30 min | Static during exam |
  | Session paths & stations | 10 min | Doesn't change during exam |
  | Examiner assignments | 5 min | Rarely changes during exam |
  | Score submissions | Don't cache | Must always write to DB |

  **Example — cache exam detail view:**
  ```python
  from django.core.cache import cache

  def exam_detail(request, exam_id):
      cache_key = f'exam_detail_{exam_id}'
      context = cache.get(cache_key)
      if not context:
          exam = get_object_or_404(Exam, pk=exam_id)
          sessions = ExamSession.objects.filter(exam=exam).order_by('session_date')
          stations = Station.objects.filter(exam=exam, active=True)
          context = {
              'exam': exam,
              'stations': list(stations),
              'sessions': list(sessions),
          }
          cache.set(cache_key, context, timeout=600)  # 10 min
      return render(request, 'creator/exams/detail.html', context)
  ```

### 5. Database Indexes

- [x] **Performance indexes created** — Migration `0022_production_indexes.py` applied
  - `idx_score_examiner_status` (StationScore)
  - `idx_score_student_station` (StationScore)
  - `idx_student_session_path` (SessionStudent)
  - `idx_student_session_status` (SessionStudent)
- [x] **Audit log indexes created** — Migration `0029` applied
  - `idx_audit_user_action` (AuditLog: user + action)
  - `idx_audit_resource` (AuditLog: resource_type + resource_id)
  - `idx_audit_dept_ts` (AuditLog: department_id + timestamp)
  - `idx_audit_action_ts` (AuditLog: action + timestamp)
  - `idx_audit_status_ts` (AuditLog: status + timestamp)

### 5b. Row-Level Security Verification (PostgreSQL only)

RLS is fully coded in migration `0027_rls_policies.py` and activates automatically.
After running migrations on PostgreSQL, verify:

- [ ] **Verify RLS is enabled on all tables:**
  ```sql
  SELECT relname, relrowsecurity, relforcerowsecurity
  FROM pg_class
  WHERE relname IN ('departments','courses','exams','exam_sessions',
                    'paths','stations','checklist_items',
                    'examiner_assignments','station_scores','item_scores');
  ```
  All rows should show `relrowsecurity=t` and `relforcerowsecurity=t`.

- [ ] **Verify helper functions exist:**
  ```sql
  SELECT proname FROM pg_proc
  WHERE proname IN ('app_role','is_global_role','is_coordinator',
                    'app_department_id','app_user_id','station_department_id',
                    'examiner_has_station','exam_department_id',
                    'session_department_id','path_department_id');
  ```
  Should return 10 functions.

- [ ] **Verify policies exist:**
  ```sql
  SELECT tablename, policyname, cmd FROM pg_policies
  WHERE schemaname = 'public' ORDER BY tablename, policyname;
  ```
  Should return 40+ policies.

- [ ] **Run RLS test matrix** (see `RLS_DESIGN.md` § 7 for full test cases)

### 5c. Celery Worker (Optional — for async audit logging)

Audit logging works **synchronously by default**. Celery is only needed if you
want audit writes to be non-blocking (recommended for exam day with 1000+ users).

- [ ] **Set `CELERY_BROKER_URL` in App Service** (reuse the same Redis)
  ```
  CELERY_BROKER_URL=rediss://:ACCESS_KEY@yourredis.redis.cache.windows.net:6380/0
  ```

- [ ] **Start Celery worker** (choose one approach):
  - **Option A — Azure WebJob:** Add a `run.sh` script that runs `celery -A osce_project worker -l info`
  - **Option B — Same App Service:** Update Procfile to include worker:
    ```
    web: gunicorn osce_project.wsgi:application --config gunicorn.conf.py
    worker: celery -A osce_project worker -l info --concurrency 2
    ```
  - **Option C — No Celery:** Leave `CELERY_BROKER_URL` empty. Audit writes happen synchronously (adds ~5ms per request).

### 5d. Audit Log Archival

- [ ] **Schedule recurring archive job** (monthly or quarterly)
  ```bash
  python manage.py archive_old_logs --days 365 --batch-size 1000
  ```
  - Use Azure WebJob (scheduled) or manual run
  - Moves AuditLog rows older than N days to AuditLogArchive table
  - Use `--dry-run` first to preview

### 6. Score Submission Optimization

- [x] **`mark_item()` optimized** — Uses `update_or_create` instead of manual filter→create/update in `examiner/views/api.py`

- [x] **Bulk score writes implemented** — `batch_mark_items()` endpoint added at `POST /api/score/:id/items/`
  Uses `bulk_create(update_conflicts=True)` for single-query upsert of all checklist items.
  URL: `examiner/api_urls.py` → `batch_mark_items`

### 7. Sentry Error Monitoring

- [x] **Sentry SDK installed** — `sentry-sdk[django]` in `requirements.txt`
- [x] **Sentry configured in `production.py`** — reads `SENTRY_DSN` env var, 10% trace sampling
- [ ] **Create Sentry account** at [sentry.io](https://sentry.io) (free tier: 5K errors/mo)
- [ ] **Set `SENTRY_DSN` in App Service** environment variables
- [ ] **Test error reporting** — trigger a test error and verify it appears in Sentry dashboard

### 8. SEO & Search Engine Blocking

**CRITICAL:** This is a private exam management system. It **MUST NOT** be indexed by Google, Bing, or other search engines.

- [ ] **Create `robots.txt`** — Place at `static/robots.txt`:
  ```
  User-agent: *
  Disallow: /
  ```
  - Configure Django to serve it: Add to `urls.py`:
    ```python
    from django.views.generic import TemplateView
    
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    ```

- [ ] **Add meta tag to base template** — In `templates/base.html` `<head>`:
  ```html
  <meta name="robots" content="noindex, nofollow" />
  ```

- [ ] **Disable sitemap** — If you have a `sitemap.xml`, delete it or return 404. Add to `urls.py`:
  ```python
  path('sitemap.xml', lambda request: HttpResponseNotFound()),
  ```

- [ ] **Set X-Robots-Tag header on all responses** — In `production.py` or middleware:
  ```python
  # In middleware or settings
  SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
  # Add to response headers in middleware:
  response['X-Robots-Tag'] = 'noindex, nofollow'
  ```

- [ ] **Disable Google Search Console** — If the domain is ever registered with Google Search Console, remove it from there

- [ ] **Monitor for indexing** — After deployment:
  - [ ] Run `site:your-azure-domain.com` in Google search → should return 0 results
  - [ ] Check Azure App Service logs for any indexing bot requests (User-Agent: Googlebot, Bingbot, etc.)
  - [ ] If indexed, submit removal request via Google Search Console

**Reason:** Exam content, student grades, and examiner assignments are sensitive data. Public indexing would be a serious **HIPAA/FERPA violation** and **data breach risk**.

---

## 🟢 P2 — RECOMMENDED (Before or Shortly After Launch)

### 8. Backup & Disaster Recovery

- [ ] **Enable Azure automated backups**
  - [ ] PostgreSQL Flexible Server → Backup → Verify retention (default 7 days, extend to 30)
  - [ ] Or configure manual backup script:
    ```bash
    pg_dump $DATABASE_URL | gzip > /backups/osce_$(date +%Y-%m-%d).sql.gz
    ```
  - [ ] Upload backups to Azure Blob Storage for off-site redundancy

- [ ] **Test restore procedure**
  - [ ] Restore a backup to a staging database
  - [ ] Verify data integrity
  - [ ] Document restore steps

- [ ] **Define recovery targets**
  - RPO (max data loss): 24 hours (daily backups) or less with point-in-time restore
  - RTO (max downtime): 4 hours

### 9. Monitoring & Uptime

- [ ] **Set up Azure Monitor alerts**
  - [ ] CPU > 80% for 5 min → email alert
  - [ ] Memory > 85% → email alert
  - [ ] HTTP 5xx errors > 10/min → email alert
  - [ ] PostgreSQL connections > 80% → email alert

- [ ] **Set up UptimeRobot** (free, [uptimerobot.com](https://uptimerobot.com))
  - [ ] Ping app every 5 minutes
  - [ ] Alert via email/SMS if down

### 10. Security Hardening

- [x] **Django security headers configured** — HSTS, SSL redirect, secure cookies, CSP in `production.py`
- [x] **Rate limiting configured** — django-axes (10 attempts, 10min lockout)
- [x] **Log rotation configured** — RotatingFileHandler (10MB, 5 backups) in `production.py`
- [x] **Stronger password validators** — MinLength 10, in `production.py`
- [x] **Row-Level Security** — PostgreSQL-level data isolation per department (migration 0027)
- [x] **RBAC** — Role-based access control on all 140+ endpoints (`core/utils/permissions.py`)
- [x] **Audit trail** — 37 action types with old/new value diffs, auto-logged via signals + middleware
- [x] **Unauthorized access logging** — 401/403/404 responses auto-logged to audit trail

- [x] **Run Django deploy check** — All 6 warnings (HSTS, SSL redirect, SECRET_KEY, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, DEBUG) are already resolved in `production.py`. Warnings only appear under development settings.

- [ ] **Azure network security**
  - [ ] PostgreSQL → Networking → Allow only App Service VNet (deny public access)
  - [ ] Redis → Firewall → Allow only App Service VNet
  - [ ] App Service → Networking → Set access restrictions if needed

- [ ] **Verify least-privilege DB user** (see step 1 above)

### 11. Load Testing

- [x] **Locust load test script created** — `scripts/locustfile.py`
  Simulates examiner workflow: login → fetch students → fetch checklist → batch mark items → submit score.
  - [x] Install Locust: `pip install locust`
  - [x] Load test script created at `scripts/locustfile.py`
  - [ ] Run against staging (NOT production): `locust -f scripts/locustfile.py --host=https://staging-url`
  - [ ] Verify < 200ms response time under load

### 12. CI/CD Pipeline (GitHub Actions)

- [x] **Created `.github/workflows/deploy.yml`** — Two-stage pipeline:
  1. **Test job** (runs on all pushes + PRs): checkout → setup Python 3.13 → install deps → `manage.py check` → `manage.py test` → `collectstatic`
  2. **Deploy job** (main branch only): checkout → install deps → `collectstatic` → deploy to Azure App Service → run migrations
- [ ] **Add publish profile** to GitHub repo secrets (`AZURE_WEBAPP_PUBLISH_PROFILE`)

---

## 🧹 Pre-Deploy Cleanup

### One-off Scripts

- [x] **Deleted `check_db_schema.py`**
- [x] **Deleted `check_soft_deleted_stations.py`**
- [x] **Deleted `delete_soft_deleted_station.py`**
- [x] **Deleted `restore_from_flask.py`**

### Configuration Files Created

- [x] **`Procfile`** — `web: gunicorn osce_project.wsgi:application --config gunicorn.conf.py` (add `worker:` line if using Celery)
- [x] **`runtime.txt`** — `python-3.13.12`
- [x] **`gunicorn.conf.py`** — gthread workers, auto CPU detection, max-requests recycling, structured logging
- [x] **`.env.example`** — All production env vars documented with examples

### Files to Verify Before Deploy

- [x] **Confirmed `db.sqlite3` is in `.gitignore`** — Also removed from git tracking (`git rm --cached`)
- [x] **Confirmed `venv/` is in `.gitignore`**
- [x] **Dev logs cleared** — `logs/audit.log` and `logs/auth.log` emptied
- [ ] **`scripts/seed_demo_data.py`** — Never run against production DB
- [ ] Production install uses `requirements.txt` only (not `requirements-dev.txt`)

### Optional Cleanup

- [ ] Review `SECURITY_PERFORMANCE_AUDIT.md` — may duplicate `SECURITY_AUDIT_REPORT.md` + `PERFORMANCE_OPTIMIZATION_REPORT.md` (delete if redundant)
- [ ] Review `AZURE_DEPLOYMENT_GUIDE.md` — update or merge into this file

---

## 📋 Testing Before Go-Live

### Functional Testing
- [ ] Test full exam workflow (create → activate → mark → complete → reports)
- [ ] Test PDF/XLSX/CSV exports
- [ ] Test bulk student/examiner uploads
- [ ] Test offline sync workflow on tablets

### Browser Compatibility
- [x] Chrome (desktop & tablet)
- [x] Safari (iPad — common for OSCE tablets)
- [x] Firefox
- [x] Edge

### Security Scanning
- [x] Run `python manage.py check --deploy` — All warnings resolved in `production.py`
- [ ] Verify CSRF protection on all forms
- [ ] Test rate limiting (10 failed login attempts → lockout)
- [ ] Verify no sensitive data in logs
---

## 📊 Database Security — What's at Risk

| Table | Data | Risk if Compromised |
|-------|------|---------------------|
| `examiners` | Usernames + hashed passwords + roles | Staff account takeover |
| `audit_logs` | Full action history, IP addresses, old/new values | Compliance data leak |
| `audit_logs_archive` | Archived audit records | Same as audit_logs |
| `login_audit_logs` | Login history, IP addresses | Privacy violation |
| `user_sessions` | Active session keys | Session hijacking |
| `session_students` | Student names + registration numbers | Student PII leak |
| `station_scores` / `item_scores` | Exam grades | Grade tampering / leak |
| `exams` / `stations` | Exam content, checklists | Exam content exposure |

**Mitigations:**
- Azure PostgreSQL only accessible from App Service VNet (deny public access)
- App connects as least-privilege DB user (not admin/superuser)
- Row-Level Security (RLS) enforced at PostgreSQL level — coordinators see only their department's data
- All passwords 16+ chars with mixed case + numbers + symbols
- Regular encrypted backups with tested restore procedure
- Comprehensive audit trail (37 action types) with old/new value tracking

---

## ✅ Go-Live Checklist

### Pre-Launch (1 week before)
- [ ] Azure App Service deployed and running
- [ ] PostgreSQL Flexible Server + PgBouncer enabled
- [ ] Migrations applied to production DB
- [ ] RLS policies verified: `SELECT * FROM pg_policies WHERE schemaname = 'public';`
- [ ] RLS helper functions verified: `SELECT app_role();`
- [ ] Superuser created
- [ ] `SECRET_KEY` in App Service environment (not in code)
- [ ] `DEBUG = False` with `ALLOWED_HOSTS` set
- [ ] HTTPS working (Azure managed certificate)
- [ ] `collectstatic` run
- [ ] Sentry configured and tested
- [ ] Celery worker running (or sync fallback confirmed)
- [ ] `CELERY_BROKER_URL` set if using async audit writes
- [ ] Audit logging verified (login/logout events appear in AuditLog)
- [ ] Backups enabled (7+ day retention)
- [ ] `python manage.py check --deploy` passes with 0 warnings (all resolved in `production.py`)
- [ ] Load testing passed (50+ concurrent users) — Locust script ready at `scripts/locustfile.py`
- [ ] Staff trained

### Launch Day
- [ ] Final deployment from `main` branch
- [ ] Smoke test all critical features
- [ ] Monitor Sentry for errors
- [ ] Monitor Azure Monitor for resource usage
- [ ] Be available for support

### Post-Launch (1 week after)
- [ ] Review Sentry error logs daily
- [ ] Monitor performance metrics
- [ ] Review audit logs in admin (check for UNAUTHORIZED_ACCESS events)
- [ ] Run `python manage.py archive_old_logs --dry-run` to preview archival
- [ ] Schedule recurring `archive_old_logs --days 365` (Azure WebJob or cron)
- [ ] Gather user feedback
- [ ] Document lessons learned

---

## 🎯 Success Criteria

Production is successfully deployed when:

1. Application accessible via HTTPS with valid certificate
2. PostgreSQL with PgBouncer handling concurrent writes
3. RLS policies active (non-superuser DB role, `FORCE ROW LEVEL SECURITY` on all tables)
4. Audit logging operational (37 action types, login/logout/CRUD tracked)
5. Database backups automated and restore tested
6. Sentry error monitoring configured and verified
7. Load testing passes with 50+ concurrent users
8. `manage.py check --deploy` passes with 0 warnings
9. Staff trained and dry run completed

---

## 📞 Support Contacts

**Development Team:** [Add contact info]
**Azure Admin:** [Add contact info]
**Emergency Escalation:** [Add contact info]

---



**Already configured in code (just need Azure services provisioned):**
- `production.py` — DATABASE_URL (via dj-database-url), REDIS_URL, SENTRY_DSN, security headers, log rotation
- `gunicorn.conf.py` — gthread workers, auto CPU detection, max-requests recycling
- `Procfile` + `runtime.txt` — PaaS-ready
- `.env.example` — All required env vars documented with examples
- Migration `0022_production_indexes.py` — Performance indexes applied
- Migration `0027_rls_policies.py` — RLS helper functions + 40+ policies (auto-activates on PostgreSQL)
- Migration `0029` — Enhanced AuditLog schema + AuditLogArchive
- `core/utils/permissions.py` — Full RBAC system with role-based decorators on all endpoints
- `core/models/audit.py` — 37 action-type constants, AuditLog + AuditLogArchive models
- `core/utils/audit.py` — AuditLogService with hierarchy-aware department resolution
- `core/tasks.py` — Celery task for async audit writes (falls back to sync when CELERY_BROKER_URL not set)
- `core/middleware.py` — UnauthorizedAccessMiddleware + RLSSessionMiddleware
- `core/signals.py` — Automatic audit logging for all CRUD on hierarchy models
- `core/management/commands/archive_old_logs.py` — Move old AuditLog rows to archive
- `osce_project/celery.py` — Celery app configuration (auto-discovered tasks)
- `RLS_DESIGN.md` — Full RLS design document with test matrix and deployment checklist
- `examiner/views/api.py` — `mark_item()` optimized with `update_or_create`, `batch_mark_items()` bulk endpoint added
- `.github/workflows/deploy.yml` — CI/CD pipeline (test + deploy)
- `scripts/locustfile.py` — Locust load test script for 50-100 concurrent examiners

**What remains is Azure resource provisioning, not code changes.**
