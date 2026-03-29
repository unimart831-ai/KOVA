web: bash start.sh
worker: celery -A config worker --loglevel=info --concurrency=2
beat: celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
