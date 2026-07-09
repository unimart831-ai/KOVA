from .celery import app as celery_app

import config.checks  # noqa: F401 — registers deploy checks

__all__ = ("celery_app",)
