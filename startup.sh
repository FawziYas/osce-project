#!/bin/bash
# Azure App Service startup script.
# Strategy: prefer the Oryx-built antenv (fastest start); fall back to a
# persistent venv in /home/site/pyenv if antenv is absent.

WWWROOT="/home/site/wwwroot"
ANTENV="$WWWROOT/antenv"
VENV_DIR="/home/site/pyenv"
REQUIREMENTS="$WWWROOT/requirements.txt"

cd "$WWWROOT"

if [ -d "$ANTENV" ]; then
  # Oryx already built the virtualenv during deployment — just use it.
  echo ">>> Activating Oryx antenv at $ANTENV"
  # shellcheck disable=SC1091
  source "$ANTENV/bin/activate"
else
  # Oryx didn't build (e.g., OneDeploy) — create/reuse our own venv.
  MARKER="$VENV_DIR/.installed_marker"
  if [ ! -d "$VENV_DIR" ] || [ ! -f "$MARKER" ] || [ "$REQUIREMENTS" -nt "$MARKER" ]; then
    echo ">>> Building venv at $VENV_DIR (this takes a few minutes on first boot)..."
    python -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS" --upgrade --quiet
    touch "$MARKER"
    echo ">>> Venv ready."
  fi
  echo ">>> Activating venv at $VENV_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
fi

export PYTHONPATH="$WWWROOT:$PYTHONPATH"

# Collect static files (WhiteNoise needs the manifest).
echo ">>> Collecting static files ..."
python manage.py collectstatic --noinput 2>&1 || echo "WARNING: collectstatic failed."

# Run migrations using admin DB user if available (needs ALTER TABLE permissions).
echo ">>> Running migrations ..."
if [ -n "$ADMIN_DATABASE_URL" ]; then
  DATABASE_URL="$ADMIN_DATABASE_URL" python manage.py migrate --noinput 2>&1 \
    || echo "WARNING: migrate failed, gunicorn will still start."
else
  python manage.py migrate --noinput 2>&1 \
    || echo "WARNING: migrate failed, gunicorn will still start."
fi

# Start Gunicorn
echo ">>> Starting gunicorn ..."
exec gunicorn osce_project.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --config "$WWWROOT/gunicorn.conf.py"
