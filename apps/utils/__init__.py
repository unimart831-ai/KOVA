import threading

from django.conf import settings


def fire_task(task, *args, **kwargs):
    """
    Fire a Celery task asynchronously.

    In production (with a real broker), uses task.delay() as normal.
    In dev with CELERY_TASK_ALWAYS_EAGER, runs the task in a daemon thread
    so the HTTP request returns immediately instead of blocking.
    """
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        threading.Thread(target=task, args=args, kwargs=kwargs, daemon=True).start()
    else:
        task.delay(*args, **kwargs)
