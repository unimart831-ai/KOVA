"""
Celery tasks for the agents app.

Periodic tasks that run agent operations on schedules.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="agents.run_daily_research")
def run_daily_research():
    """
    Periodic task: Run the Research Agent for all active users.
    Dispatches each user as a separate sub-task with staggered countdown
    to avoid OpenRouter rate limits.
    """
    from apps.agents.models import AgentConfig
    from apps.billing.models import get_plan_limits

    users_with_research = User.objects.filter(
        Q(onboarding_completed=True) | Q(posts__status="published"),
        agent_configs__agent_type="research",
        agent_configs__is_active=True,
    ).distinct()

    dispatched = 0
    for idx, user in enumerate(users_with_research):
        plan = getattr(getattr(user, "profile", None), "plan", "starter")
        if "research" not in get_plan_limits(plan).get("agents_enabled", []):
            continue
        # Stagger by 5s per user to avoid OpenRouter rate limits (429s)
        _run_research_for_user.apply_async(args=[user.pk], countdown=idx * 5)
        dispatched += 1

    if dispatched:
        logger.info("Daily research dispatched %d user tasks", dispatched)
    return dispatched


@shared_task(name="agents.run_research_for_user", max_retries=1, acks_late=True)
def _run_research_for_user(user_id):
    """Run the Research Agent for a single user (dispatched as sub-task)."""
    from apps.agents.research_agent import discover_trends

    user = User.objects.get(pk=user_id)
    try:
        result = discover_trends(user)
        if result.get("trending_topics"):
            logger.info("Research complete for %s: %d topics", user.email, len(result["trending_topics"]))
    except Exception as e:
        logger.error("Research Agent failed for %s: %s", user.email, e)


@shared_task(name="agents.run_engage_cycle")
def run_engage_cycle():
    """
    Periodic task: Run the Engage Agent cycle for all active users.
    Dispatches each user as a separate sub-task for parallel execution.
    Runs every 30 minutes.
    """
    from apps.agents.models import AgentConfig
    from apps.billing.models import get_plan_limits

    users_with_engage = User.objects.filter(
        Q(onboarding_completed=True) | Q(posts__status="published"),
        agent_configs__agent_type="engage",
        agent_configs__is_active=True,
    ).distinct()

    dispatched = 0
    for user in users_with_engage:
        plan = getattr(getattr(user, "profile", None), "plan", "starter")
        if not get_plan_limits(plan).get("engagement_agent", False):
            continue
        _run_engage_for_user.delay(user.pk)
        dispatched += 1

    if dispatched:
        logger.info("Engage cycle dispatched %d user tasks", dispatched)
    return dispatched


@shared_task(name="agents.run_engage_for_user", max_retries=1, acks_late=True)
def _run_engage_for_user(user_id):
    """Run the engage cycle for a single user (dispatched as sub-task)."""
    from apps.agents.engage_agent import run_engage_cycle as engage_cycle

    user = User.objects.get(pk=user_id)
    try:
        result = engage_cycle(user)
        if result.get("fetched", 0) > 0 or result.get("replies_generated", 0) > 0:
            logger.info(
                "Engage cycle for %s: fetched=%d, analyzed=%d, replies=%d, auto_sent=%d",
                user.email, result["fetched"], result["analyzed"],
                result["replies_generated"], result["auto_sent"],
            )
        else:
            logger.debug(
                "Engage cycle for %s: no new interactions (fetched=%d, analyzed=%d)",
                user.email, result.get("fetched", 0), result.get("analyzed", 0),
            )
    except Exception as e:
        logger.error("Engage cycle failed for %s: %s", user.email, e)


@shared_task(name="agents.run_strategy_cycle")
def run_strategy_cycle():
    """
    Periodic task: Run the Chief Strategist Agent for all active users.
    Gathers intelligence from all agents, makes strategic decisions,
    and creates proactive content seeds.
    Runs once daily (early morning, before daily briefs).
    """
    from apps.agents.models import AgentConfig
    from apps.agents.strategist_agent import run_strategy_cycle as strategist_cycle
    from apps.billing.models import get_plan_limits

    users_with_strategist = User.objects.filter(
        Q(onboarding_completed=True) | Q(posts__status="published"),
        agent_configs__agent_type="strategist",
        agent_configs__is_active=True,
    ).distinct()

    processed = 0
    for idx, user in enumerate(users_with_strategist):
        try:
            plan = getattr(getattr(user, "profile", None), "plan", "starter")
            if "strategist" not in get_plan_limits(plan).get("agents_enabled", []):
                continue
            # Stagger between users to avoid OpenRouter rate limits (429s)
            if idx > 0:
                import time
                time.sleep(5)
            result = strategist_cycle(user)
            if result.get("status") == "completed":
                processed += 1
                logger.info(
                    "Strategy cycle for %s: seeds=%d, recommendations=%d",
                    user.email,
                    result.get("seeds_created", 0),
                    len(result.get("recommendations", [])),
                )
        except Exception as e:
            logger.error("Strategy cycle failed for %s: %s", user.email, e)

    if processed:
        logger.info("Strategy cycle complete: %d users processed", processed)
    return processed


@shared_task(name="agents.measure_agent_outcomes")
def measure_agent_outcomes():
    """
    Periodic task: Score past agent actions against actual outcomes.
    This is the engine that closes the feedback loop — comparing what agents
    did against what actually happened (engagement, user edits, rejections).

    Runs daily. Retroactively scores Create Agent and Strategist actions
    from the last 7 days that haven't been measured yet.
    """
    from apps.agents.memory import (
        measure_create_agent_outcomes,
        measure_strategist_outcomes,
    )

    users = User.objects.filter(
        Q(onboarding_completed=True) | Q(posts__status="published"),
    ).distinct()

    total_create = 0
    total_strategy = 0

    for user in users:
        try:
            total_create += measure_create_agent_outcomes(user)
            total_strategy += measure_strategist_outcomes(user)
        except Exception as e:
            logger.error("Outcome measurement failed for %s: %s", user.email, e)

    logger.info(
        "Agent outcomes measured: %d create actions, %d strategy actions scored",
        total_create, total_strategy,
    )
    return {"create_scored": total_create, "strategy_scored": total_strategy}
