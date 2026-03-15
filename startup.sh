#!/bin/bash

# Azure App Service startup script for Django OSCE

# Run migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
gunicorn osce_project.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --config gunicorn.conf.py
