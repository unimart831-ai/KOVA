import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


def run_task_inline(task, *args, **kwargs):
    """Run a Celery task callable in a daemon thread (bypasses the broker)."""
    threading.Thread(target=task, args=args, kwargs=kwargs, daemon=True).start()


def fire_task(task, *args, queue=None, **kwargs):
    """
    Dispatch a Celery task without blocking the web request.

    - With a real broker (Redis): sends via Celery — worker picks it up.
    - Without a broker (CELERY_TASK_ALWAYS_EAGER or empty broker URL): runs the task
      in a daemon thread so the HTTP response returns immediately.
    - If the broker is configured but unreachable, falls back to inline so web
      requests (onboarding, studio submit) never crash on Redis downtime.
    """
    broker = getattr(settings, "CELERY_BROKER_URL", "") or ""
    always_eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)

    if always_eager or not broker:
        run_task_inline(task, *args, **kwargs)
        return

    try:
        task.apply_async(args=args, kwargs=kwargs, queue=queue or "default")
    except Exception:
        logger.warning(
            "Celery broker unavailable for %s — running inline",
            getattr(task, "name", task),
            exc_info=True,
        )
        run_task_inline(task, *args, **kwargs)
