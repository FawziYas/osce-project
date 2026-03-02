"""
Gunicorn production configuration.
https://docs.gunicorn.org/en/stable/settings.html
"""
import multiprocessing
import os

# ── Server socket ──────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# ── Worker processes ───────────────────────────────────────────
# For I/O-bound Django (DB queries), use gthread worker class.
# workers × threads = max concurrent requests.
workers = int(os.environ.get('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
worker_class = 'gthread'

# ── Timeouts ───────────────────────────────────────────────────
timeout = 120           # Kill worker if silent for 2 min (report generation)
graceful_timeout = 30   # Allow 30s for in-flight requests on shutdown
keepalive = 5           # Keep TCP connections alive for 5s

# ── Worker lifecycle ───────────────────────────────────────────
max_requests = 1000             # Restart worker after 1000 requests (prevent leaks)
max_requests_jitter = 50        # Random jitter to avoid all workers restarting at once
preload_app = True              # Load app before forking workers (saves memory)

# ── Logging ────────────────────────────────────────────────────
accesslog = '-'                 # Log to stdout (captured by PaaS/systemd)
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" %(D)sμs'

# ── Security ───────────────────────────────────────────────────
limit_request_line = 8190       # Max URL length
limit_request_fields = 100      # Max header fields
limit_request_field_size = 8190 # Max header field size

# ── Forwarded headers ─────────────────────────────────────────
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS', '*')
proxy_protocol = False
