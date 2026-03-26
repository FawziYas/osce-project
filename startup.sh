#!/bin/bash
# Azure App Service startup script.
#
# Oryx compressed deployment (--compress-destination-dir) extracts the build
# to a temp path (e.g. /tmp/<uid>/) and sets CWD there before calling this
# script. Non-compressed deployments (OneDeploy) use /home/site/wwwroot.
# We derive APP_PATH from CWD so both modes work correctly.

WWWROOT="/home/site/wwwroot"
APP_PATH="$(pwd)"
VENV_DIR="/home/site/pyenv"
REQUIREMENTS="$APP_PATH/requirements.txt"

echo ">>> App root: $APP_PATH"

# Find antenv: Oryx compressed mode places it in the extracted temp dir;
# non-compressed mode places it directly in wwwroot.
if [ -d "$APP_PATH/antenv" ]; then
  echo ">>> Activating Oryx antenv at $APP_PATH/antenv"
  # shellcheck disable=SC1091
  source "$APP_PATH/antenv/bin/activate"
elif [ -d "$WWWROOT/antenv" ]; then
  echo ">>> Activating Oryx antenv at $WWWROOT/antenv"
  # shellcheck disable=SC1091
  source "$WWWROOT/antenv/bin/activate"
else
  # Oryx didn't build (e.g., OneDeploy) — create/reuse our own venv.
  REQUIREMENTS="$WWWROOT/requirements.txt"
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

export PYTHONPATH="$APP_PATH:$PYTHONPATH"

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
  --config "$APP_PATH/gunicorn.conf.py"
