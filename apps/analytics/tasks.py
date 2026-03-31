"""
Analytics Celery tasks — Competitor intelligence + metrics.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="analyze-competitor")
def analyze_competitor_task(user_id, competitor_id):
    """Run AI analysis on a single competitor."""
    from apps.accounts.models import User
    from apps.analytics.competitor_intel import analyze_competitor
    from apps.analytics.models import Competitor

    try:
        user = User.objects.get(id=user_id)
        competitor = Competitor.objects.get(id=competitor_id, user=user)
        analysis = analyze_competitor(user, competitor)
        if analysis:
            logger.info("Competitor analysis complete: %s for %s", competitor.name, user.email)
        return str(analysis.id) if analysis else None
    except Exception as e:
        logger.exception("analyze_competitor_task failed: %s", e)
        return None


@shared_task(name="analyze-all-competitors")
def analyze_all_competitors():
    """
    Periodic task: analyze all active competitors for all users.
    Runs weekly via Celery Beat.
    """
    from datetime import timedelta

    from apps.accounts.models import User
    from apps.analytics.models import Competitor

    cutoff = timezone.now() - timedelta(days=6)  # Don't re-analyze within 6 days

    from django.db.models import Q
    competitors = Competitor.objects.filter(
        is_active=True,
    ).filter(
        Q(last_analyzed_at__isnull=True) | Q(last_analyzed_at__lt=cutoff)
    ).select_related("user")

    count = 0
    for comp in competitors:
        # Check user has active subscription (don't analyze for free users)
        profile = getattr(comp.user, "profile", None)
        if not profile:
            continue

        analyze_competitor_task.delay(str(comp.user_id), str(comp.id))
        count += 1

    logger.info("Queued %d competitor analyses", count)
    return count
