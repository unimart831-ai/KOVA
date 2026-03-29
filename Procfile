web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
worker: celery -A config worker --loglevel=info --concurrency=2
beat: celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
