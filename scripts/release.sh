#!/bin/bash
# Railway release phase — apply pending Django migrations before traffic switch.
set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"

echo "==> [release] DATABASE_URL set: $(if [ -n "${DATABASE_URL:-}" ]; then echo 'YES'; else echo 'NO'; fi)"
echo "==> [release] Running pending migrations..."
python manage.py migrate --noinput
echo "==> [release] Migrations complete."
