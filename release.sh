#!/bin/bash
# Railway release phase — apply pending Django migrations before traffic switch.
set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"

echo "==> [release] DATABASE_URL set: $(if [ -n "${DATABASE_URL:-}" ]; then echo 'YES'; else echo 'NO'; fi)"
echo "==> [release] Running pending migrations..."
python manage.py migrate --noinput
echo "==> [release] Migrations complete."

echo "==> [release] Pruning stale beat tasks..."
python manage.py prune_stale_beat_tasks --delete || echo "==> [release] WARNING: beat prune skipped"
echo "==> [release] Beat task prune complete."

echo "==> [release] Ensuring Site row exists..."
python -c "
import django, os
django.setup()
from django.contrib.sites.models import Site
domain = os.environ.get('SITE_DOMAIN', 'kovaagents-production.up.railway.app')
name = os.environ.get('SITE_NAME', 'Kova Agent')
Site.objects.update_or_create(id=1, defaults={'domain': domain, 'name': name})
print(f'    Site ready: {name} ({domain})')
"
echo "==> [release] Done."
