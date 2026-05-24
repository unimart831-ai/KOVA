"""Buffer PageView analytics in Redis — flushed to Postgres via Celery."""

import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

BUFFER_KEY = "analytics:pageview_buffer"
MAX_BUFFER = 500


def buffer_pageview(user_id, section: str, path: str) -> None:
    """Append a page view to the Redis buffer (non-blocking)."""
    try:
        entry = json.dumps({
            "user_id": str(user_id),
            "section": section[:50],
            "path": path[:500],
        })
        client = cache.client.get_client()
        client.rpush(BUFFER_KEY, entry)
        if client.llen(BUFFER_KEY) >= MAX_BUFFER:
            from apps.analytics.tasks import flush_pageview_buffer
            flush_pageview_buffer.delay()
    except Exception:
        logger.debug("PageView buffer append failed", exc_info=True)


def drain_pageview_buffer(batch_size: int = 200) -> int:
    """Pop up to batch_size entries and return as list of dicts."""
    try:
        client = cache.client.get_client()
        pipe = client.pipeline()
        for _ in range(batch_size):
            pipe.lpop(BUFFER_KEY)
        raw_items = pipe.execute()
    except Exception:
        logger.debug("PageView buffer drain failed", exc_info=True)
        return 0

    from apps.analytics.models import PageView

    rows = []
    for raw in raw_items:
        if not raw:
            continue
        try:
            data = json.loads(raw)
            rows.append(PageView(
                user_id=data["user_id"],
                section=data["section"],
                path=data["path"],
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    if rows:
        PageView.objects.bulk_create(rows)
    return len(rows)
