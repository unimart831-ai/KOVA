"""
Analytics Celery tasks — Competitor intelligence + metrics.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="analyze-competitor")
def analyze_competitor_task(user_id, competitor_id):
    """Run AI analysis on a single competitor, then alert on high-priority insights."""
    from apps.accounts.models import User
    from apps.analytics.competitor_intel import analyze_competitor
    from apps.analytics.models import Competitor

    try:
        user = User.objects.get(id=user_id)
        competitor = Competitor.objects.get(id=competitor_id, user=user)
        analysis = analyze_competitor(user, competitor)
        if analysis:
            logger.info("Competitor analysis complete: %s for %s", competitor.name, user.email)
            _send_competitor_alerts(user, competitor, analysis)
        return str(analysis.id) if analysis else None
    except Exception as e:
        logger.exception("analyze_competitor_task failed: %s", e)
        return None


def _send_competitor_alerts(user, competitor, analysis):
    """Create notifications for high-priority competitor insights."""
    from datetime import timedelta

    from apps.analytics.models import CompetitorInsight
    from apps.notifications.models import Notification

    recent_insights = CompetitorInsight.objects.filter(
        competitor=competitor,
        created_at__gte=timezone.now() - timedelta(minutes=10),
        priority__in=["high", "critical"],
    )

    for insight in recent_insights[:3]:
        message = f"🔔 Competitor alert: {competitor.name} — {insight.title}"
        try:
            Notification.create_for_user(
                user=user,
                notification_type=Notification.NotificationType.AGENT_ACTION,
                message=message,
            )
        except Exception:
            logger.exception("Failed to create competitor alert notification")


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
