#!/bin/bash
set -e

export DJANGO_SETTINGS_MODULE="config.settings.production"

echo "==> Checking if output.css exists..."
if [ -f ./static/css/output.css ]; then
    echo "    Found ./static/css/output.css ($(wc -c < ./static/css/output.css) bytes)"
else
    echo "    output.css NOT found in static/css/ - building Tailwind..."
    npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify 2>&1 || echo "WARNING: tailwind build failed"
fi

echo "==> Collecting static files..."
python manage.py collectstatic --noinput 2>&1

echo "==> Verifying staticfiles directory..."
if [ -d ./staticfiles ]; then
    echo "    staticfiles/ exists"
    ls staticfiles/css/ 2>/dev/null && echo "    CSS files found" || echo "    WARNING: No CSS in staticfiles/"
else
    echo "    ERROR: staticfiles/ does not exist after collectstatic!"
fi

echo "==> Running migrations..."
echo "    DATABASE_URL is set: $(if [ -n \"$DATABASE_URL\" ]; then echo 'YES'; else echo 'NO - THIS IS THE PROBLEM'; fi)"
echo "    DB host: $(echo $DATABASE_URL | sed 's/.*@\(.*\):.*/\1/' 2>/dev/null || echo 'could not parse')"
python manage.py migrate --noinput 2>&1 || echo "WARNING: migrate failed"

echo "==> Seeding reel music beds (FFmpeg placeholders if missing)..."
python manage.py seed_reel_music_beds 2>&1 || echo "WARNING: reel music seed failed"

echo "==> Creating superuser (if not exists)..."
python manage.py create_superuser 2>&1

echo "==> Setting Site domain..."
python -c "
import django; django.setup()
from django.contrib.sites.models import Site
import os
domain = os.environ.get('SITE_DOMAIN', 'kovaagents-production.up.railway.app')
name = os.environ.get('SITE_NAME', 'Kova Agent')
site = Site.objects.get_or_create(id=1)[0]
if site.domain != domain or site.name != name:
    site.domain = domain
    site.name = name
    site.save()
    print(f'    Site updated: {name} ({domain})')
else:
    print(f'    Site OK: {name} ({domain})')
" 2>&1

echo "==> Checking storage backend..."
python -c "
import django; django.setup()
from django.core.files.storage import default_storage
print(f'    Storage backend: {default_storage.__class__.__name__}')
from django.conf import settings
bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
if bucket:
    print(f'    R2 bucket: {bucket}')
    print(f'    R2 endpoint: {getattr(settings, \"AWS_S3_ENDPOINT_URL\", \"<NOT SET>\")}')
else:
    print('    WARNING: R2 NOT configured — using local FileSystemStorage')
" 2>&1

echo "==> Starting Daphne (HTTP + WebSocket) on port ${PORT:-8000}..."
exec daphne config.asgi:application --bind 0.0.0.0 --port ${PORT:-8000}
