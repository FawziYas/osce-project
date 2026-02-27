# Production Deployment Checklist

**Project:** Django OSCE Exam System
**Status:** Ready for Production Deployment
**Last Updated:** February 25, 2026

---

## ⚡ Key Production Changes (Mandatory — Any Host)

These 5 changes are **non-negotiable** before going live:

| # | Change | Why | How |
|---|--------|-----|-----|
| 1 | **SQLite → PostgreSQL** | SQLite locks the entire DB on writes — concurrent examiners scoring will fail | Install `psycopg2-binary`, set `DATABASE_URL` env var, run `migrate` |
| 2 | **`DEBUG = False`** + **`ALLOWED_HOSTS`** | `DEBUG = True` exposes tracebacks, settings, passwords to anyone | Set in `.env` or environment variables |
| 3 | **WhiteNoise for static files** | Django's `runserver` static serving is not for production | `pip install whitenoise`, add middleware, run `collectstatic` |
| 4 | **Gunicorn as WSGI server** | `runserver` is single-threaded, no security hardening | `gunicorn osce_project.wsgi:application --workers 4` |
| 5 | **`SECRET_KEY` from environment variable** | Hardcoded key in code = anyone with repo access can forge sessions | `SECRET_KEY = os.environ['SECRET_KEY']` |

---

## 🌐 Recommended Hosting: Railway or Render

### Option A: Railway (Recommended for Simplicity)

**What it is:** Managed PaaS — push to GitHub and it deploys automatically.

**Steps:**
1. Go to [railway.app](https://railway.app) → Sign in with GitHub
2. Click "New Project" → "Deploy from GitHub Repo" → select `osce-project`
3. Add a **PostgreSQL** plugin (click "+ New" → "Database" → "PostgreSQL")
4. Railway auto-creates `DATABASE_URL` environment variable
5. Add environment variables:
   - `SECRET_KEY` = (generate a random key)
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `your-app.up.railway.app`
6. Add a `Procfile` to your repo:
   ```
   web: gunicorn osce_project.wsgi:application --bind 0.0.0.0:$PORT --workers 4
   ```
7. Add a `runtime.txt`:
   ```
   python-3.13.2
   ```
8. Push → Railway builds and deploys automatically

**Pricing:** ~$5/mo for hobby, ~$20/mo for production (includes PostgreSQL)
**Free tier:** $5 credit/month (enough for testing)

### Option B: Render (Best Free Tier)

**What it is:** Similar to Railway, GitHub-connected auto-deploy.

**Steps:**
1. Go to [render.com](https://render.com) → Sign in with GitHub
2. Create **New Web Service** → connect `osce-project` repo
3. Settings:
   - **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start Command:** `gunicorn osce_project.wsgi:application`
4. Create **New PostgreSQL** database → copy the Internal Database URL
5. Add environment variables:
   - `DATABASE_URL` = (paste the internal URL)
   - `SECRET_KEY` = (generate a random key)
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `your-app.onrender.com`

**Pricing:** Free tier (spins down after 15min inactivity — slow cold start), $7/mo for always-on
**PostgreSQL:** Free for 90 days (1GB), then $7/mo

### What You Need to Add to Your Repo for Either Host

1. `Procfile` — tells the host how to run your app
2. `runtime.txt` — specifies Python version
3. Update `settings.py` to read from environment variables
4. Add `whitenoise`, `gunicorn`, `psycopg2-binary` to `requirements.txt`
5. Add `dj-database-url` to parse `DATABASE_URL` automatically

---

## � 500 Concurrent Examiners — High-Performance Production Setup

**Target:** 500 examiners scoring simultaneously with < 200ms response time.

### Architecture Overview

```
                    ┌─────────────┐
                    │  Cloudflare  │  ← CDN + DDoS protection + SSL
                    │    (Free)    │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │   Railway    │  ← Auto-scaling web service
                    │  (Gunicorn)  │
                    │  8 workers   │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ PgBouncer│ │  Redis   │ │  Static  │
        │(Pooling) │ │ (Cache)  │ │  (CDN)   │
        └────┬─────┘ └──────────┘ └──────────┘
             │
        ┌────┴─────┐
        │PostgreSQL │  ← Managed DB (Railway or Neon)
        │  Primary  │
        └──────────┘
```

### Step-by-Step Setup Checklist

#### 1. Web Server — Gunicorn with 8+ Workers

- [ ] **Configure Gunicorn for high concurrency**

  Update `Procfile`:
  ```
  web: gunicorn osce_project.wsgi:application --bind 0.0.0.0:$PORT --workers 8 --threads 4 --worker-class gthread --timeout 120 --max-requests 1000 --max-requests-jitter 50
  ```

  | Setting | Value | Why |
  |---------|-------|-----|
  | `--workers 8` | 8 worker processes | Each handles ~60 concurrent connections |
  | `--threads 4` | 4 threads per worker | 8 × 4 = 32 simultaneous requests |
  | `--worker-class gthread` | Threaded workers | Better for I/O-bound Django (DB queries) |
  | `--timeout 120` | 2 min timeout | Prevents hung workers during report generation |
  | `--max-requests 1000` | Restart worker after 1000 requests | Prevents memory leaks |

  **Capacity:** 8 workers × 4 threads = **32 simultaneous requests**. With avg 200ms response time, that's **~160 requests/second** → easily handles 500 users.

#### 2. PostgreSQL — Connection Pooling (Critical)

- [ ] **Install and configure PgBouncer**

  Without pooling, 500 examiners = 500 DB connections → PostgreSQL max is 100 by default → **crash**.

  **On Railway:** Add PgBouncer plugin (click "+ New" → search "PgBouncer")

  **In Django `settings.py`:**
  ```python
  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.postgresql',
          'NAME': os.environ.get('PGDATABASE'),
          'USER': os.environ.get('PGUSER'),
          'PASSWORD': os.environ.get('PGPASSWORD'),
          'HOST': os.environ.get('PGHOST'),
          'PORT': os.environ.get('PGPORT', '5432'),
          'CONN_MAX_AGE': 600,       # Reuse connections for 10 minutes
          'CONN_HEALTH_CHECKS': True, # Check connection before using
          'OPTIONS': {
              'connect_timeout': 10,
          },
      }
  }
  ```

  | Setting | Value | Why |
  |---------|-------|-----|
  | `CONN_MAX_AGE = 600` | Reuse connections for 10 min | Avoids opening/closing DB connection per request |
  | `CONN_HEALTH_CHECKS = True` | Verify connection is alive | Prevents "connection closed" errors |
  | PgBouncer pool size | 25 connections | 25 persistent connections shared across 500 users |

#### 3. Redis Cache — Eliminate Repetitive Database Queries

- [ ] **Add Redis for caching**

  **On Railway:** Click "+ New" → "Database" → "Redis"

  **Install packages:**
  ```bash
  pip install django-redis redis
  ```

  **Add to `settings.py`:**
  ```python
  CACHES = {
      'default': {
          'BACKEND': 'django_redis.cache.RedisCache',
          'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
          'OPTIONS': {
              'CLIENT_CLASS': 'django_redis.client.DefaultClient',
          },
          'TIMEOUT': 300,  # 5 minutes default
      }
  }

  # Use Redis for Django sessions (faster than DB sessions)
  SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
  SESSION_CACHE_ALIAS = 'default'
  ```

- [ ] **Cache expensive queries in views**

  What to cache (these queries are called hundreds of times during exam):

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

#### 4. Database Indexes — Speed Up Common Queries

- [ ] **Add indexes for examiner scoring queries**

  These are the hottest queries during exam day (500 examiners hitting them simultaneously):

  ```python
  # Add to core/models as Meta indexes or create a migration

  # StationScore — examiner looks up their assigned scores
  class StationScore(models.Model):
      class Meta:
          indexes = [
              models.Index(fields=['session', 'station', 'student']),
              models.Index(fields=['examiner', 'session']),
              models.Index(fields=['student', 'session']),
          ]

  # ItemScore — individual checklist item scores
  class ItemScore(models.Model):
      class Meta:
          indexes = [
              models.Index(fields=['station_score', 'checklist_item']),
          ]

  # SessionStudent — student lookup per session
  class SessionStudent(models.Model):
      class Meta:
          indexes = [
              models.Index(fields=['session', 'path']),
          ]
  ```

  Run: `python manage.py makemigrations && python manage.py migrate`

#### 5. Static Files — CDN (Cloudflare)

- [ ] **Serve static files via Cloudflare CDN (Free)**

  1. Register domain on [cloudflare.com](https://cloudflare.com) (free plan)
  2. Point DNS to Railway/Render
  3. Enable caching for `/static/` → CSS, JS, images served from edge servers worldwide
  4. Examiners' browsers load static files from nearest Cloudflare server, not your Django app

  **Result:** Django only handles API/scoring requests, not serving CSS/JS files → **50% less server load**

  **In Django `settings.py`:**
  ```python
  # WhiteNoise with compression + caching headers
  STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
  ```

#### 6. Optimize Score Submission (The Hottest Endpoint)

- [ ] **Batch score writes**

  During exam, the #1 bottleneck is score submission — 500 examiners submitting scores every 8 minutes (per station rotation).

  **Current:** Each checklist item = 1 DB write → 10 items × 500 examiners = 5000 writes in 30 seconds

  **Optimized:** Use `bulk_create` / `bulk_update`:
  ```python
  # Instead of:
  for item in checklist_items:
      ItemScore.objects.create(station_score=score, checklist_item=item, points=points)

  # Do:
  scores_to_create = [
      ItemScore(station_score=score, checklist_item=item, points=points)
      for item, points in checklist_items
  ]
  ItemScore.objects.bulk_create(scores_to_create)
  ```

  **Result:** 10 individual DB writes → 1 batch write = **10x faster**

#### 7. Django Middleware Optimization

- [ ] **Remove unnecessary middleware for speed**

  ```python
  MIDDLEWARE = [
      'django.middleware.security.SecurityMiddleware',
      'whitenoise.middleware.WhiteNoiseMiddleware',     # Static files
      # 'django.middleware.locale.LocaleMiddleware',    # Remove if single language
      'django.contrib.sessions.middleware.SessionMiddleware',
      'django.middleware.common.CommonMiddleware',
      'django.middleware.csrf.CsrfViewMiddleware',
      'django.contrib.auth.middleware.AuthenticationMiddleware',
      'django.contrib.messages.middleware.MessageMiddleware',
      # 'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Remove if no iframes
      'axes.middleware.AxesMiddleware',                 # Login rate limiting
  ]
  ```

#### 8. Monitoring — Know Before Users Complain

- [ ] **Add Sentry for error tracking ($0 — free tier)**
  ```bash
  pip install sentry-sdk
  ```
  ```python
  import sentry_sdk
  sentry_sdk.init(
      dsn=os.environ.get('SENTRY_DSN'),
      traces_sample_rate=0.1,  # 10% of requests for performance monitoring
  )
  ```

- [ ] **Add UptimeRobot for uptime monitoring ($0 — free)**
  - Ping your app every 5 minutes
  - Alert via email/SMS if down

---

### 500 Examiners — Final Cost Breakdown

| Component | Service | Monthly Cost |
|-----------|---------|-------------|
| Web Server | Railway (Pro plan, 8 workers) | $20 |
| PostgreSQL | Railway managed PostgreSQL | Included |
| Connection Pooling | PgBouncer on Railway | $5 |
| Redis Cache | Railway Redis or RedisCloud | $10 |
| CDN + SSL | Cloudflare (free plan) | $0 |
| Error Monitoring | Sentry (free tier) | $0 |
| Uptime Monitoring | UptimeRobot (free) | $0 |
| **Total** | | **~$35/month** |

### Expected Performance at 500 Concurrent Examiners

| Metric | Without Optimization | With Full Setup |
|--------|---------------------|-----------------|
| Score submission | 800ms | **< 150ms** |
| Exam detail page | 500ms | **< 100ms** (cached) |
| Login | 300ms | **< 200ms** |
| Report generation | 5s | **< 2s** |
| Max concurrent users | ~100 (then crash) | **500+ stable** |
| DB connections used | 500 (exhausted) | **25 via PgBouncer** |

### Implementation Priority Order

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🔴 P0 | PostgreSQL + PgBouncer | Without this, 100+ users = crash | 1 hour |
| 🔴 P0 | Gunicorn 8 workers + threads | Without this, 1 request at a time | 5 min |
| 🟡 P1 | Redis cache for exam data | 50% fewer DB queries | 2 hours |
| 🟡 P1 | Database indexes | 5x faster scoring queries | 30 min |
| 🟡 P1 | Bulk score writes | 10x faster score submission | 1 hour |
| 🟢 P2 | Cloudflare CDN | 50% less server load (static files) | 30 min |
| 🟢 P2 | Sentry monitoring | Know about errors before users report | 15 min |

---

## �🚀 Phase 8: Production Deployment

### 1. Database Setup

- [ ] **Set up PostgreSQL Production Database**
  - [ ] Install PostgreSQL 15+ on production server or use managed service (AWS RDS, Azure Database, etc.)
  - [ ] Create database: `osce_production`
  - [ ] Create database user with appropriate permissions
  - [ ] Configure connection pooling (recommended: pgBouncer)
  - [ ] Test connection from application server

- [ ] **Configure Database Connection**
  - [ ] Update `.env` file with `DATABASE_URL=postgresql://user:password@host:5432/osce_production`
  - [ ] Run migrations: `python manage.py migrate`
  - [ ] Verify all tables created successfully
  - [ ] Create superuser: `python manage.py createsuperuser`

- [ ] **Database Performance**
  - [ ] Verify indexes are created (check migration 0001_initial)
  - [ ] Configure database backups (daily automated backups)
  - [ ] Test database restore procedure
  - [ ] Set up query monitoring (pg_stat_statements)

### 2. Web Server Configuration

- [ ] **Install Production Dependencies**
  ```bash
  pip install -r requirements-production.txt
  ```
  - [ ] Django 6.0.2
  - [ ] gunicorn (WSGI server)
  - [ ] psycopg2-binary (PostgreSQL adapter)
  - [ ] whitenoise (static file serving)
  - [ ] django-axes (rate limiting)

- [ ] **Configure Gunicorn**
  - [ ] Create gunicorn config file: `/etc/gunicorn/osce.conf.py`
  - [ ] Set workers: `workers = (2 * CPU_cores) + 1`
  - [ ] Set worker class: `worker_class = 'sync'`
  - [ ] Configure timeout: `timeout = 120` (for long-running reports)
  - [ ] Set bind address: `bind = '127.0.0.1:8000'`

  **systemd service:**
  ```ini
  [Unit]
  Description=OSCE Gunicorn
  After=network.target

  [Service]
  User=osce
  WorkingDirectory=/var/www/osce
  ExecStart=/var/www/osce/venv/bin/gunicorn osce_project.wsgi:application --workers 4 --bind unix:/run/osce.sock
  Restart=always

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] **Configure Nginx (Reverse Proxy)**
  - [ ] Install Nginx
  - [ ] Create site configuration: `/etc/nginx/sites-available/osce`
  - [ ] Configure proxy_pass to Gunicorn
  - [ ] Set up static file serving: `/static/` → `/path/to/staticfiles/`
  - [ ] Configure `client_max_body_size: 20M` (for XLSX uploads)
  - [ ] Enable gzip compression
  - [ ] Enable site: `ln -s /etc/nginx/sites-available/osce /etc/nginx/sites-enabled/`
  - [ ] Test config: `nginx -t` then `systemctl reload nginx`

- [ ] **Run as System Service**
  - [ ] Create systemd service file: `/etc/systemd/system/osce.service`
  - [ ] Enable service: `systemctl enable osce`
  - [ ] Start service: `systemctl start osce`

### 3. SSL/TLS Configuration

- [ ] **Obtain SSL Certificate (Let's Encrypt — Free)**
  ```bash
  sudo apt install certbot python3-certbot-nginx
  sudo certbot --nginx -d yourdomain.com
  ```
  - [ ] Configure auto-renewal cron job
  - [ ] Test SSL: https://www.ssllabs.com/ssltest/

- [ ] **Update Django Settings**
  ```python
  SECURE_SSL_REDIRECT = True
  SESSION_COOKIE_SECURE = True
  CSRF_COOKIE_SECURE = True
  SECURE_HSTS_SECONDS = 31536000
  SECURE_HSTS_INCLUDE_SUBDOMAINS = True
  ```

### 4. Environment Configuration

- [ ] **Production .env File**
  - [ ] ⚠️ **Set `DEBUG=False`** (CRITICAL)
  - [ ] Generate strong `SECRET_KEY`:
    ```bash
    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    ```
  - [ ] Set `ALLOWED_HOSTS=['yourdomain.com', 'www.yourdomain.com']`
  - [ ] Configure `DATABASE_URL` with production PostgreSQL credentials
  - [ ] ⚠️ **All passwords must be STRONG** (16+ chars, uppercase + lowercase + numbers + symbols)
  - [ ] Set secure file permissions: `chmod 600 .env`
  - [ ] Add `.env` to `.gitignore` (verify not committed to repo)

- [ ] **Collect Static Files**
  ```bash
  python manage.py collectstatic --no-input
  ```

### 5. Security Hardening

- [ ] **Firewall Configuration**
  - [ ] Enable UFW: allow ports 80, 443, 22 (SSH — limited IPs only)
  - [ ] Block direct access to port 5432 (PostgreSQL) from external
  - [ ] Block direct access to port 8000 (Gunicorn)

- [ ] **Server Security**
  - [ ] Disable root SSH login
  - [ ] Use SSH keys instead of passwords
  - [ ] Configure fail2ban for SSH brute-force protection
  - [ ] Keep system packages updated: `apt update && apt upgrade`

- [ ] **Django Security Checklist**
  - [ ] Run: `python manage.py check --deploy` — fix ALL warnings
  - [ ] Verify CSRF protection on all forms
  - [ ] Verify rate limiting on login page

### 6. Database Security — Risk Awareness

The production database contains everything in one place. Protect accordingly:

| Table | Data | Risk if Compromised |
|-------|------|---------------------|
| `examiners` | Usernames + hashed passwords + roles | Staff account takeover |
| `login_audit_logs` | Login history, IP addresses | Privacy violation |
| `user_sessions` | Active session keys | Session hijacking |
| `session_students` | Student names + registration numbers | Student PII leak |
| `station_scores` / `item_scores` | Exam grades | Grade tampering / leak |
| `exams` / `stations` | Exam content, checklists | Exam content exposure |

**Mitigations:**
- DB only accessible from localhost (firewall block 5432 externally)
- App connects as least-privilege DB user (not superuser):
  ```sql
  CREATE USER osce_app WITH PASSWORD 'strong_password';
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO osce_app;
  ```

### 7. Backup & Disaster Recovery

- [ ] **Automated Encrypted Nightly Backups**
  ```bash
  #!/bin/bash
  DATE=$(date +%Y-%m-%d_%H-%M)
  pg_dump osce_db | gzip | gpg --symmetric --passphrase "$GPG_PASSPHRASE" \
    -o /backups/osce_$DATE.sql.gz.gpg
  # Upload to S3 / Google Drive / etc.
  ```
  Schedule via cron: `0 2 * * * /home/osce/backup.sh`

- [ ] **Disaster Recovery Plan**
  - [ ] Configure backup retention policy (30 days)
  - [ ] Test restore procedure monthly
  - [ ] Define RTO (Recovery Time Objective): target 4 hours
  - [ ] Define RPO (Recovery Point Objective): target 24 hours
  - [ ] Back up Nginx/Gunicorn configs and `.env`

### 8. Monitoring & Logging

- [ ] **Application Error Monitoring (Sentry)**
  ```bash
  pip install sentry-sdk
  ```
  - [ ] Configure DSN in settings.py
  - [ ] Test error reporting works

- [ ] **System Monitoring**
  - [ ] Monitor CPU/Memory/Disk usage
  - [ ] Monitor database connections
  - [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
  - [ ] Configure alerts for critical thresholds

- [ ] **Log Management**
  - [ ] Configure Django logging to file
  - [ ] Set up log rotation (logrotate)
  - [ ] Configure Gunicorn and Nginx access/error logs

### 9. Testing & Quality Assurance

- [ ] **Load Testing**
  - [ ] Simulate 50–100 concurrent examiners
  - [ ] Test scoring submission under load
  - [ ] Test report generation under load
  - [ ] Tools: Apache Bench, Locust, or JMeter

- [ ] **Browser Compatibility Testing**
  - [ ] Chrome (desktop & tablet)
  - [ ] Firefox
  - [ ] Safari (iPad)
  - [ ] Edge

- [ ] **Security Scanning**
  - [ ] Run OWASP ZAP scan
  - [ ] Run `python manage.py check --deploy`
  - [ ] Verify no sensitive data in logs
  - [ ] Test CSRF token on all forms
  - [ ] Test rate limiting (5 failed login attempts → lockout)

- [ ] **Functional Testing**
  - [ ] Test full exam workflow (create → activate → mark → complete → reports)
  - [ ] Test PDF/XLSX/CSV exports
  - [ ] Test bulk student/examiner uploads
  - [ ] Test offline sync workflow on tablets

### 10. Audit Logging (Deferred)

- [ ] Create `AuditLog` model and migration
- [ ] Implement `core.middleware.AuditLoggingMiddleware`
- [ ] Log all login/logout events, score submissions, session state changes
- [ ] Register in Django Admin as read-only

### 11. Documentation

- [ ] Server specifications (CPU, RAM, disk)
- [ ] Installation steps and configuration file locations
- [ ] Service management commands (start/stop/restart)
- [ ] Backup/restore procedures
- [ ] Troubleshooting common issues
- [ ] Update EXAMINER_MOBILE_GUIDE.md with production URL
- [ ] Update EXAM_DAY_QUICKREF.md

### 12. Training & Handoff

- [ ] Train coordinators on creator interface
- [ ] Train examiners on tablet interface
- [ ] Conduct dry run with real exam scenario
- [ ] Transfer access credentials securely
- [ ] Document who has access to what
- [ ] Define support hours (24/7 during exams?)

---

## ✅ Go-Live Checklist

### Pre-Launch (1 week before)
- [ ] SQLite → PostgreSQL migrated and tested
- [ ] `SECRET_KEY` in environment variable (not in code)
- [ ] `DEBUG = False` with `ALLOWED_HOSTS` set
- [ ] DB user has least-privilege permissions
- [ ] Nightly backup script working and tested restore
- [ ] HTTPS enabled with valid SSL certificate
- [ ] Static files served via Nginx
- [ ] Gunicorn running as systemd service
- [ ] Firewall: only ports 80, 443, 22 open
- [ ] `python manage.py check --deploy` passes with 0 warnings
- [ ] Load testing passed
- [ ] Security scan passed
- [ ] Staff trained

### Launch Day
- [ ] Final production deployment
- [ ] Smoke test all critical features
- [ ] Monitor error logs closely
- [ ] Monitor system resources
- [ ] Be available for support

### Post-Launch (1 week after)
- [ ] Review error logs daily
- [ ] Monitor performance metrics
- [ ] Gather user feedback
- [ ] Document lessons learned

---

## 🎯 Success Criteria

Production is considered successfully deployed when:

1. ✅ Application accessible via HTTPS with valid certificate
2. ✅ Database backups automated and tested
3. ✅ Error monitoring (Sentry) configured
4. ✅ Load testing passes with 50+ concurrent users
5. ✅ Staff trained and comfortable with interface
6. ✅ All security checks passing (`manage.py check --deploy`)
7. ✅ Uptime monitoring active with alerts configured

---

## 📞 Support Contacts

**Development Team:** [Add contact info]
**Operations Team:** [Add contact info]
**Database Admin:** [Add contact info]
**Emergency Escalation:** [Add contact info]

---

## 📝 Notes

- Development server: http://127.0.0.1:8000/
- Development database: SQLite at `osce_project/db.sqlite3`
- Production database: PostgreSQL (to be configured)
- All migrations ready and tested
- Security audit completed

---

> ⚠️ This file replaces the old OSCE_Exam_DEV/PRODUCTION_TODO.md — all content merged here.

---

## 1. Database — Switch from SQLite to PostgreSQL

SQLite is **not suitable for production** (no concurrent write support, no network access, no proper permissions).

**Install on server:**
```bash
sudo apt install postgresql postgresql-contrib
createdb osce_db
createuser osce_user
```

**Update `osce_project/settings/production.py`:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'osce_db',
        'USER': 'osce_user',
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

**Install Python driver:**
```bash
pip install psycopg2-binary
```

**Migrate:**
```bash
python manage.py migrate
```

---

## 2. SECRET_KEY — Move to Environment Variable

**Never hardcode** `SECRET_KEY` in settings. Anyone who sees the codebase can forge sessions.

**In production settings:**
```python
import os
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
```

**Generate a strong key:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Set it as a system environment variable on the server (not in code).**

---

## 3. DEBUG = False

```python
# settings/production.py
DEBUG = False

ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com', '192.168.x.x']
```

Without this, Django will expose stack traces and internal config to users on errors.

---

## 4. Database User Permissions — Least Privilege

The app should **not** connect to the DB as a superuser.

```sql
-- PostgreSQL
CREATE USER osce_app WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE osce_db TO osce_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO osce_app;
```

- App user can read/write data
- App user **cannot** DROP tables, CREATE users, or access pg_catalog
- Only DBA/admin can do structural changes

---

## 5. Encrypted Nightly Backups

One database = one failure point. Must have:

**Script: `backup.sh`**
```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d_%H-%M)
pg_dump osce_db | gzip | gpg --symmetric --passphrase "$GPG_PASSPHRASE" -o /backups/osce_$DATE.sql.gz.gpg
# Upload to off-site storage (S3, Google Drive, etc.)
```

**Schedule via cron:**
```bash
0 2 * * * /home/osce/backup.sh   # Daily at 2AM
```

**Verify backups monthly** — test restore to staging.

---

## 6. Database in Context — What's at Risk

The production database will contain:

| Table | Data | Risk if Compromised |
|-------|------|---------------------|
| `examiners` | Usernames + hashed passwords + roles | Staff account takeover |
| `login_audit_logs` | Login history, IP addresses | Privacy violation |
| `user_sessions` | Active session keys | Session hijacking |
| `session_students` | Student names + registration numbers | Student PII leak |
| `station_scores` / `item_scores` | Exam grades | Grade tampering / leak |
| `exams` / `stations` | Exam content, checklists | Exam content exposure |

**Single DB is acceptable for this scale**, but protect it with:
- Strong DB password
- No public DB port (firewall block port 5432)
- DB only accessible from localhost or internal network
- Regular encrypted backups

---

## 7. HTTPS — Force SSL

```python
# settings/production.py
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
```

Use **Nginx + Let's Encrypt (Certbot)** for free SSL:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 8. Static Files — Serve via Nginx (Not Django)

```python
# settings/production.py
STATIC_ROOT = '/var/www/osce/static/'
MEDIA_ROOT = '/var/www/osce/media/'
```

```bash
python manage.py collectstatic
```

Nginx serves `/static/` directly without hitting Django — much faster.

---

## 9. Gunicorn — Replace Django Dev Server

```bash
pip install gunicorn
gunicorn osce_project.wsgi:application --workers 4 --bind 0.0.0.0:8000
```

**systemd service:**
```ini
[Unit]
Description=OSCE Gunicorn
After=network.target

[Service]
User=osce
WorkingDirectory=/var/www/osce
ExecStart=/var/www/osce/venv/bin/gunicorn osce_project.wsgi:application --workers 4 --bind unix:/run/osce.sock
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 10. Pre-Launch Checklist

- [ ] SQLite → PostgreSQL migrated and tested
- [ ] `SECRET_KEY` in environment variable (not code)
- [ ] `DEBUG = False` with `ALLOWED_HOSTS` set
- [ ] DB user has least-privilege permissions
- [ ] Nightly backup script working and tested
- [ ] HTTPS enabled with valid SSL certificate
- [ ] Static files served via Nginx
- [ ] Gunicorn running as systemd service
- [ ] Firewall: only ports 80, 443, 22 open
- [ ] DB port 5432 blocked from external access
- [ ] `python manage.py check --deploy` passes with no warnings

---

## Run Django Deployment Check

```bash
python manage.py check --deploy
```

This reports all security issues before you go live.

---

## 🗑️ Cleanup — Delete Unused & Unnecessary Files Before Production

These files exist in the repo for development purposes only and must be removed (or excluded from the production deploy) before going live.

### One-off Scripts at Project Root (safe to delete)

These scripts were used once during development/migration and serve no ongoing purpose:

| File | Why it can be deleted |
|------|-----------------------|
| `check_db_schema.py` | One-off DB inspection script — no longer needed |
| `check_soft_deleted_stations.py` | One-off debugging helper — no longer needed |
| `delete_soft_deleted_station.py` | One-off data-fix script — already applied, no longer needed |
| `restore_from_flask.py` | Flask → Django migration script — migration is complete |

```bash
# Run from project root
del check_db_schema.py
del check_soft_deleted_stations.py
del delete_soft_deleted_station.py
del restore_from_flask.py
```

---

### Demo / Seed Data Script (do NOT run in production)

| File | Action |
|------|--------|
| `scripts/seed_demo_data.py` | Keep the file for reference, but **never run it in production** — it inserts fake Arabic students, exams, and checklist items into whatever database is configured. Add a production guard at the top if keeping it. |

---

### Development Database — Never Deploy to Production

| File | Why |
|------|-----|
| `db.sqlite3` | This is the **local development SQLite database** (contains demo data, test exams, dev users). It must not be copied to the production server. Production uses PostgreSQL. Make sure `db.sqlite3` is listed in `.gitignore` and never committed or uploaded. |

Verify it is ignored:
```bash
git check-ignore -v db.sqlite3
# Should output: .gitignore:...  db.sqlite3
```

---

### Log Files — Rotate Before Production Launch

Log files in `logs/` accumulate dev-session noise and should be cleared (not deleted — the folder must stay):

| File | Action |
|------|--------|
| `logs/audit.log` (~40 KB of dev activity) | Clear contents before production launch |
| `logs/auth.log` (~2.5 KB of dev logins) | Clear contents before production launch |

```bash
# Clear log contents but keep the files (Django needs them to exist)
echo $null > logs\audit.log
echo $null > logs\auth.log
```

Set up log rotation in production so they don't grow unbounded:
- Use `logging.handlers.RotatingFileHandler` in `settings.py` (max 10 MB, keep 5 backups)
- Or let the OS handle it via `logrotate` (Linux) / Task Scheduler (Windows Server)

---

### Duplicate Documentation Files (optional cleanup)

| File | Note |
|------|------|
| `SECURITY_PERFORMANCE_AUDIT.md` | Appears to duplicate content from both `SECURITY_AUDIT_REPORT.md` and `PERFORMANCE_OPTIMIZATION_REPORT.md`. Review and delete if redundant. |

---

### Local Virtual Environment — Never Deploy

| Path | Action |
|------|--------|
| `venv/` | Local Python virtual environment. Must not be uploaded to any server. Production uses its own environment created from `requirements.txt`. Confirm `venv/` is in `.gitignore`. |

---

### Dev-only Requirements — Do Not Install in Production

| File | Action |
|------|--------|
| `requirements-dev.txt` | Contains dev tools (e.g. `ipython`, `django-debug-toolbar`). Production `pip install` should only use `requirements.txt`. |

```bash
# Production install — dev deps excluded
pip install -r requirements.txt
```

---

### Quick Pre-Deploy Cleanup Checklist

- [ ] Deleted `check_db_schema.py`
- [ ] Deleted `check_soft_deleted_stations.py`
- [ ] Deleted `delete_soft_deleted_station.py`
- [ ] Deleted `restore_from_flask.py`
- [ ] Confirmed `db.sqlite3` is in `.gitignore` and NOT committed
- [ ] Cleared `logs/audit.log` and `logs/auth.log`
- [ ] Confirmed `venv/` is excluded from deployment
- [ ] Production install uses `requirements.txt` only (not `requirements-dev.txt`)
- [ ] `scripts/seed_demo_data.py` has NOT been run against the production database
