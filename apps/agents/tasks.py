"""
Celery tasks for the agents app.

Periodic tasks that run agent operations on schedules.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

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
    now = timezone.now()
    for idx, user in enumerate(users_with_research):
        plan = getattr(getattr(user, "profile", None), "plan", "starter")
        if "research" not in get_plan_limits(plan).get("agents_enabled", []):
            continue

        # New users (first 7 days) get priority scheduling — dispatched first
        # with shorter delays to ensure they get rich research data quickly
        days_since_signup = (now - user.date_joined).days
        is_new_user = days_since_signup <= 7

        if is_new_user:
            countdown = idx * 3  # Tighter spacing for new users
        else:
            countdown = idx * 5  # Standard stagger

        _run_research_for_user.apply_async(args=[user.pk], countdown=countdown)
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
            logger.info(
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


# ─── Growth Intelligence ─────────────────────────────────────────────────────

# Maps platform → (API method to call, kwargs builder, response key for followers, following key, posts key)
_FOLLOWER_SOURCES = {
    "tiktok": {
        "method": "get_account_insights",
        "followers_key": "followers",
        "following_key": "following",
        "posts_key": "total_videos",
    },
    "instagram": {
        "method": "get_account_insights",
        "kwargs_fn": lambda acct: {
            "ig_user_id": (acct.metadata or {}).get("ig_business_id", ""),
        },
        "followers_key": "follower_count",
    },
    "facebook": {
        "method": "get_account_insights",
        "kwargs_fn": lambda acct: {
            "page_id": (acct.metadata or {}).get("page_id", ""),
            "page_access_token": (acct.metadata or {}).get("page_access_token", acct.access_token),
        },
        "followers_key": "page_fan_adds",  # FB returns delta, not total — fallback to metadata
        "use_metadata_followers": True,
    },
}

# Platforms where follower data lives in SocialAccount.metadata (set at OAuth/refresh)
_METADATA_PLATFORMS = {
    "linkedin": {"followers_key": "followers_count", "following_key": None},
    "bluesky": {"followers_key": "followers_count", "following_key": "following_count", "posts_key": "posts_count"},
    "pinterest": {"followers_key": "follower_count", "posts_key": "pin_count"},
    "youtube": {"followers_key": "subscriber_count", "posts_key": "video_count"},
    "twitter": {"followers_key": "followers_count", "following_key": "following_count"},
    "threads": {"followers_key": "followers_count"},
}


def _extract_follower_count(data, key):
    """Safely extract a numeric follower count from API response or metadata."""
    val = data.get(key, 0) if data else 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


@shared_task(name="agents.track_audience_growth")
def track_audience_growth():
    """
    Daily task: Snapshot follower/audience counts for all active social accounts.
    This powers the Strategist Agent's growth intelligence — correlating content
    with audience growth, identifying growth velocity, and spotting stagnation.
    """
    from datetime import date

    from apps.analytics.models import GrowthSnapshot
    from apps.platforms.models import SocialAccount
    from apps.platforms.providers import get_provider

    today = date.today()
    accounts = SocialAccount.objects.filter(
        is_active=True,
    ).select_related("user")

    created = 0
    skipped = 0

    for account in accounts:
        # Skip if already tracked today
        if GrowthSnapshot.objects.filter(social_account=account, snapshot_date=today).exists():
            skipped += 1
            continue

        followers = 0
        following = 0
        posts_count = 0
        platform = account.platform

        try:
            provider = get_provider(platform)
            if not provider:
                # Fallback to metadata
                meta = account.metadata or {}
                followers = _extract_follower_count(meta, "followers_count") or _extract_follower_count(meta, "follower_count") or _extract_follower_count(meta, "subscriber_count")
                following = _extract_follower_count(meta, "following_count") or _extract_follower_count(meta, "follows_count")
                posts_count = _extract_follower_count(meta, "posts_count") or _extract_follower_count(meta, "video_count") or _extract_follower_count(meta, "pin_count")
            elif platform in _FOLLOWER_SOURCES:
                # Platform with get_account_insights API
                source = _FOLLOWER_SOURCES[platform]
                method = getattr(provider, source["method"], None)
                if method:
                    kwargs = {}
                    if "kwargs_fn" in source:
                        kwargs = source["kwargs_fn"](account)
                    data = method(account.access_token, **kwargs)
                    if not data.get("error"):
                        followers = _extract_follower_count(data, source["followers_key"])
                        following = _extract_follower_count(data, source.get("following_key", ""))
                        posts_count = _extract_follower_count(data, source.get("posts_key", ""))

                # FB insights returns page_fan_adds (delta), not total — use metadata
                if source.get("use_metadata_followers") or not followers:
                    meta = account.metadata or {}
                    for key in ("followers_count", "follower_count", "subscriber_count"):
                        val = _extract_follower_count(meta, key)
                        if val:
                            followers = val
                            break
            elif platform in _METADATA_PLATFORMS:
                # Platform where we read from stored metadata
                meta = account.metadata or {}
                keys = _METADATA_PLATFORMS[platform]
                followers = _extract_follower_count(meta, keys["followers_key"])
                following = _extract_follower_count(meta, keys.get("following_key", ""))
                posts_count = _extract_follower_count(meta, keys.get("posts_key", ""))

            if not followers:
                # Last resort: try metadata with common keys
                meta = account.metadata or {}
                for key in ("followers_count", "follower_count", "subscriber_count"):
                    val = _extract_follower_count(meta, key)
                    if val:
                        followers = val
                        break

        except Exception as e:
            logger.warning("Growth tracking for %s/%s failed: %s", account.platform, account.username, e)
            # Still try metadata fallback
            meta = account.metadata or {}
            followers = _extract_follower_count(meta, "followers_count") or _extract_follower_count(meta, "follower_count")

        if not followers:
            continue

        # Get previous snapshot to calculate delta
        previous = GrowthSnapshot.objects.filter(
            social_account=account,
            snapshot_date__lt=today,
        ).order_by("-snapshot_date").first()

        followers_delta = followers - previous.followers if previous else 0
        posts_delta = posts_count - previous.posts_count if previous and posts_count else 0

        GrowthSnapshot.objects.create(
            social_account=account,
            user=account.user,
            followers=followers,
            following=following,
            posts_count=posts_count,
            followers_delta=followers_delta,
            posts_delta=posts_delta,
            snapshot_date=today,
        )
        created += 1

    logger.info("Growth tracking: %d snapshots created, %d skipped (already tracked)", created, skipped)
    return {"created": created, "skipped": skipped}
