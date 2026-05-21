import threading

from django.conf import settings


def run_task_inline(task, *args, **kwargs):
    """Run a Celery task callable in a daemon thread (bypasses the broker)."""
    threading.Thread(target=task, args=args, kwargs=kwargs, daemon=True).start()


def fire_task(task, *args, **kwargs):
    """
    Dispatch a Celery task without blocking the web request.

    - With a real broker (Redis): sends via task.delay() — Celery worker picks it up.
    - Without a broker (CELERY_TASK_ALWAYS_EAGER or empty broker URL): runs the task
      in a daemon thread so the HTTP response returns immediately.
    """
    broker = getattr(settings, "CELERY_BROKER_URL", "") or ""
    always_eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)

    if always_eager or not broker:
        run_task_inline(task, *args, **kwargs)
    else:
        try:
            task.delay(*args, **kwargs)
        except Exception:
            # Broker unreachable — fall back so user-facing flows still complete.
            run_task_inline(task, *args, **kwargs)
