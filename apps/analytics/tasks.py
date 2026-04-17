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
            _auto_act_on_insights(user, competitor)
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
        priority="high",
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


def _auto_act_on_insights(user, competitor):
    """
    Auto-create ContentSeeds from high-priority competitor insights that have
    suggested content ideas. Turns intelligence into action without manual clicks.

    Limits: max 1 auto-seed per competitor per analysis to avoid flooding.
    Only acts on insights that are HIGH priority and have a content idea.
    """
    from datetime import timedelta

    from apps.analytics.models import CompetitorInsight
    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount

    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )
    if not platforms:
        return

    # Get recent high-priority insights with content ideas, not yet acted on
    insights = CompetitorInsight.objects.filter(
        user=user,
        competitor=competitor,
        priority="high",
        is_acted_on=False,
        is_dismissed=False,
        created_at__gte=timezone.now() - timedelta(minutes=10),
    ).exclude(
        suggested_content_idea=""
    ).order_by("-created_at")[:1]  # Max 1 per analysis

    for insight in insights:
        idea = (
            f"Competitive response — {competitor.name}: {insight.title}\n\n"
            f"{insight.suggested_content_idea}\n\n"
            f"Context: {insight.description[:300]}"
        )

        ContentSeed.objects.create(
            user=user,
            idea=idea,
            notes=f"Auto-created from competitor insight: {insight.title} ({competitor.name})",
            target_platforms=platforms[:3],
        )

        insight.is_acted_on = True
        insight.save(update_fields=["is_acted_on"])

        logger.info(
            "Auto-acted on competitor insight: %s — %s (user: %s)",
            competitor.name, insight.title, user.email,
        )


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
