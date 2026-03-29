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
