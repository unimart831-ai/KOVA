#!/usr/bin/env bash
# Railway build script — runs during deployment, NOT at runtime.
set -o errexit

echo "==> Installing Python dependencies..."
pip install -r requirements/production.txt

echo "==> Installing Node dependencies (Tailwind)..."
npm install

echo "==> Building Tailwind CSS..."
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Build complete!"
