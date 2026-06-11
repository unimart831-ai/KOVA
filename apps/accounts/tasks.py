"""Celery tasks for accounts app."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="accounts.snapshot_pilot_metrics")
def snapshot_pilot_metrics():
    """Nightly snapshot of TEST_BUSINESSES pilot metrics for admin dashboard."""
    from apps.accounts.pilot_metrics import compute_pilot_metrics

    payload = compute_pilot_metrics(persist_snapshot=True)
    active = payload["aggregate"]["active_test_businesses"]
    wedge = payload["aggregate"]["avg_wedge_percent"]
    logger.info(
        "Pilot metrics snapshot: %d active businesses, %.1f%% avg wedge",
        active,
        wedge,
    )
    return {
        "active_test_businesses": active,
        "avg_wedge_percent": wedge,
        "captured_at": payload["captured_at"],
    }
