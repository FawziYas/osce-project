#!/bin/bash

# Azure App Service startup script for Django OSCE

# Run migrations using admin credentials if available (needed for ALTER TABLE
# on tables created by the admin user).  Falls back to DATABASE_URL.
if [ -n "$ADMIN_DATABASE_URL" ]; then
  DATABASE_URL="$ADMIN_DATABASE_URL" python manage.py migrate --noinput
else
  python manage.py migrate --noinput
fi

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
gunicorn osce_project.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --config gunicorn.conf.py
