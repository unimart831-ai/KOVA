"""
Distributed locks for Celery Beat tasks.

Beat tasks that fan out work across all users (e.g. run_engage_cycle,
generate_all_daily_briefs) must not run concurrently with themselves: a
backed-up worker plus a fresh Beat tick will otherwise double-fire emails,
LLM calls, and publishes. We use Redis (via Django's cache) as the lock
substrate — atomic SETNX semantics with a TTL acts as the lease.

Usage:
    @shared_task(name="agents.run_engage_cycle")
    @single_run("agents.run_engage_cycle", timeout=20 * 60)
    def run_engage_cycle():
        ...

The decorator must wrap *inside* @shared_task so Celery sees the original
task signature, but the lock check runs on every invocation.
"""
from __future__ import annotations

import functools
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def single_run(lock_name: str, timeout: int = 30 * 60):
    """
    Skip the task if another instance is already running.

    The lock is taken via ``cache.add`` (atomic on Redis) and held for
    ``timeout`` seconds — pick a value generously larger than the task's
    expected runtime so a crashed worker eventually frees the slot.

    Returns ``{"skipped": True, "reason": "already running"}`` when the
    lock is already held — callers can ignore this.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"beat-lock:{lock_name}"
            acquired = cache.add(key, "1", timeout=timeout)
            if not acquired:
                logger.info(
                    "Skipping %s — another instance holds the lock", lock_name
                )
                return {"skipped": True, "reason": "already running"}
            try:
                return func(*args, **kwargs)
            finally:
                cache.delete(key)

        return wrapper

    return decorator
