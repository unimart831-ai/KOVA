release: bash release.sh
web: bash start.sh
worker: env DJANGO_SETTINGS_MODULE=config.settings.production celery -A config worker --loglevel=info --concurrency=3 -Q critical,default,low
beat: env DJANGO_SETTINGS_MODULE=config.settings.production celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
