#!/bin/bash

# Azure App Service startup script for Django OSCE
# Oryx installs packages into /home/site/wwwroot/antenv during the Kudu Zip Deploy
# build phase. When Azure runs a custom startup command the virtual environment
# is not always auto-activated, so we source it explicitly with a fallback.
if [ -f "/home/site/wwwroot/antenv/bin/activate" ]; then
  source /home/site/wwwroot/antenv/bin/activate
elif [ -f "/antenv/bin/activate" ]; then
  source /antenv/bin/activate
fi

# Run migrations using admin credentials if available (needed for ALTER TABLE
# on tables created by the admin user).  Falls back to DATABASE_URL.
if [ -n "$ADMIN_DATABASE_URL" ]; then
  DATABASE_URL="$ADMIN_DATABASE_URL" python manage.py migrate --noinput
else
  python manage.py migrate --noinput
fi

# Start Gunicorn
exec gunicorn osce_project.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --config gunicorn.conf.py
