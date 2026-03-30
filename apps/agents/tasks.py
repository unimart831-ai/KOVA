"""
Celery tasks for the agents app.

Periodic tasks that run agent operations on schedules.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="agents.run_daily_research")
def run_daily_research():
    """
    Periodic task: Run the Research Agent for all active users.
    Runs once daily (early morning) to prepare trend data before daily briefs.
    """
    from apps.agents.models import AgentConfig
    from apps.agents.research_agent import discover_trends

    # Find users with active research agents who have completed onboarding
    users_with_research = User.objects.filter(
        onboarding_completed=True,
        agent_configs__agent_type="research",
        agent_configs__is_active=True,
    ).distinct()

    researched = 0
    for user in users_with_research:
        try:
            result = discover_trends(user)
            if result.get("trending_topics"):
                researched += 1
        except Exception as e:
            logger.error("Research Agent failed for %s: %s", user.email, e)

    logger.info("Daily research complete: %d users researched", researched)
    return researched


@shared_task(name="agents.run_engage_cycle")
def run_engage_cycle():
    """
    Periodic task: Run the Engage Agent cycle for all active users.
    Fetches new interactions, analyzes sentiment, generates replies,
    and auto-responds (for users who enabled it).
    Runs every 30 minutes.
    """
    from apps.agents.engage_agent import run_engage_cycle as engage_cycle
    from apps.agents.models import AgentConfig

    users_with_engage = User.objects.filter(
        onboarding_completed=True,
        agent_configs__agent_type="engage",
        agent_configs__is_active=True,
    ).distinct()

    processed = 0
    for user in users_with_engage:
        try:
            result = engage_cycle(user)
            if result.get("fetched", 0) > 0 or result.get("replies_generated", 0) > 0:
                processed += 1
                logger.info(
                    "Engage cycle for %s: fetched=%d, analyzed=%d, replies=%d, auto_sent=%d",
                    user.email, result["fetched"], result["analyzed"],
                    result["replies_generated"], result["auto_sent"],
                )
        except Exception as e:
            logger.error("Engage cycle failed for %s: %s", user.email, e)

    logger.info("Engage cycle complete: %d users processed", processed)
    return processed
