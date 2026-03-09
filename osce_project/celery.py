"""
Celery configuration for the OSCE project.

Usage:
  celery -A osce_project worker -l info

In production, run alongside Django (Gunicorn) with a process manager
such as supervisord or systemd.
"""
import os

from celery import Celery

# Use Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings')

app = Celery('osce_project')

# Read config from Django settings, the CELERY_ namespace means all
# celery-related settings must have the `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()
