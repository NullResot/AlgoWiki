#!/bin/sh
set -eu

python <<'PY'
import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection

timeout = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
interval = float(os.getenv("DB_WAIT_INTERVAL", "2"))
deadline = time.time() + max(timeout, 1)
last_error = None

while time.time() < deadline:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        sys.exit(0)
    except Exception as exc:  # pragma: no cover - runtime bootstrap path
        last_error = exc
        time.sleep(max(interval, 0.2))

print(f"Database wait timeout after {timeout}s: {last_error}", file=sys.stderr)
sys.exit(1)
PY

python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8001 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
