"""Production health probes — DB, cache, Celery, media/LLM key configuration."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_MEDIA_KEYS = (
    ("photoroom", "PHOTOROOM_API_KEY"),
    ("bannerbear", "BANNERBEAR_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
)


def run_health_checks(*, deep: bool = False) -> dict:
    """Return component status. ``deep=True`` adds media/LLM key checks."""
    result: dict = {"ok": True, "components": {}}

    # ── Database ──
    try:
        from django.db import connection

        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        result["components"]["database"] = {"status": "ok"}
    except Exception as exc:
        result["ok"] = False
        result["components"]["database"] = {"status": "error", "detail": str(exc)[:200]}

    # ── Redis / cache ──
    try:
        from django.core.cache import cache

        probe_key = "kova:health:probe"
        cache.set(probe_key, "1", 10)
        if cache.get(probe_key) != "1":
            raise RuntimeError("cache read/write mismatch")
        result["components"]["redis"] = {"status": "ok"}
    except Exception as exc:
        result["ok"] = False
        result["components"]["redis"] = {"status": "error", "detail": str(exc)[:200]}

    if not deep:
        return result

    # ── Celery broker (best-effort) ──
    try:
        from config.celery import app as celery_app

        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1)
        result["components"]["celery_broker"] = {"status": "ok"}
    except Exception as exc:
        result["components"]["celery_broker"] = {"status": "degraded", "detail": str(exc)[:200]}

    # ── Media / LLM API keys ──
    keys_status = {}
    missing = []
    for label, setting_name in _MEDIA_KEYS:
        configured = bool(getattr(settings, setting_name, "") or "")
        keys_status[label] = "configured" if configured else "missing"
        if not configured:
            missing.append(label)

    result["components"]["media_keys"] = keys_status
    if missing and not getattr(settings, "DEBUG", False):
        result["ok"] = False
        result["components"]["media_keys_note"] = (
            f"Missing keys: {', '.join(missing)} — campaigns may fail image/carousel generation."
        )

    return result
