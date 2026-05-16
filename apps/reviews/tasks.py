"""Celery tasks for the review loop.

Hook the periodic task in `config/celery.py` beat schedule (or run it
manually): `python manage.py shell -c 'from apps.reviews.tasks import
send_due_review_requests; send_due_review_requests()'`.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from apps.reviews.models import ReviewRequest
from apps.reviews.services import send_review_request

logger = logging.getLogger(__name__)


def send_due_review_requests(batch_size: int = 50) -> int:
    """Fire outreach for all pending ReviewRequests whose time has come.
    Returns the count sent."""
    due = (
        ReviewRequest.objects.filter(
            status=ReviewRequest.Status.PENDING,
            scheduled_at__lte=timezone.now(),
        )
        .select_related("user", "lead", "booking")
        .order_by("scheduled_at")[:batch_size]
    )
    sent = 0
    for req in due:
        try:
            if send_review_request(req):
                sent += 1
        except Exception as e:
            logger.exception("Failed to send review request %s: %s", req.id, e)
            ReviewRequest.objects.filter(pk=req.pk).update(
                status=ReviewRequest.Status.FAILED,
                failure_reason=str(e)[:500],
            )
    return sent


try:
    from celery import shared_task

    @shared_task(name="reviews.send_due_review_requests")
    def send_due_review_requests_task():
        return send_due_review_requests()
except Exception:  # pragma: no cover
    pass
