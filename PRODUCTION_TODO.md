# Production Deployment Checklist

**Project:** Django OSCE Exam System
**Status:** Ready for Production Deployment
**Last Updated:** February 24, 2026

---

## 🚀 Phase 8: Production Deployment

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
