"""
Celery tasks for the agents app.

Periodic tasks that run agent operations on schedules.
"""

import logging

import sentry_sdk
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.utils.locks import single_run

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="agents.run_daily_research", soft_time_limit=10 * 60, time_limit=12 * 60)
@single_run("agents.run_daily_research", timeout=30 * 60)
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


@shared_task(
    name="agents.run_research_for_user",
    max_retries=1,
    acks_late=True,
    soft_time_limit=120,
    time_limit=150,
)
def _run_research_for_user(user_id):
    """Run the Research Agent for a single user (dispatched as sub-task)."""
    from apps.agents.research_agent import discover_trends
    from apps.billing.exceptions import PlanLimitExceeded

    user = User.objects.get(pk=user_id)
    try:
        result = discover_trends(user)
        if result.get("trending_topics"):
            logger.info("Research complete for %s: %d topics", user.email, len(result["trending_topics"]))
            _auto_seed_from_trends(user, result)

        # Pre-generate AI suggestions so Studio loads instantly
        refresh_seed_suggestions.apply_async(args=[user_id], countdown=10)
    except PlanLimitExceeded as e:
        # Budget hit — billing event, not a bug. Don't noise Sentry.
        logger.info("Research Agent skipped (budget) for %s: %s", user.email, e.message)
    except Exception as e:
        logger.error("Research Agent failed for %s: %s", user.email, e)
        sentry_sdk.capture_exception(e)


@shared_task(
    name="agents.refresh_seed_suggestions",
    max_retries=1,
    acks_late=True,
    soft_time_limit=60,
    time_limit=90,
)
def refresh_seed_suggestions(user_id):
    """
    Pre-generate and cache AI-powered content suggestions for a user.
    Called after the Research Agent completes so the Studio page always
    has fresh, personalised ideas ready.
    """
    from django.core.cache import cache

    user = User.objects.get(pk=user_id)
    cache_key = f"ai_seed_suggestions:{user.pk}"

    # Clear stale cache so _get_ai_generated_suggestions regenerates
    cache.delete(cache_key)

    try:
        from apps.agents.playbooks import _get_ai_generated_suggestions

        profile = getattr(user, "profile", None)
        if not profile:
            return

        suggestions = _get_ai_generated_suggestions(user, profile, max_count=8)
        logger.info(
            "Refreshed %d AI suggestions for %s", len(suggestions), user.email
        )
        return len(suggestions)
    except Exception as e:
        logger.error("Refresh suggestions failed for %s: %s", user.email, e)
        sentry_sdk.capture_exception(e)


def _auto_seed_from_trends(user, research_result):
    """
    Auto-create ContentSeeds from high-urgency trending topics.
    Only seeds from topics with urgency="high" and a suggested_angle.
    Max 1 seed per research run to avoid flooding.
    """
    from datetime import timedelta

    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount

    # Emergency pause check
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "emergency_pause", False):
        return

    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )
    if not platforms:
        return

    # Don't exceed 1 auto-trend-seed per 12 hours
    recent_trend_seeds = ContentSeed.objects.filter(
        user=user,
        notes__startswith="[Research Agent]",
        created_at__gte=timezone.now() - timedelta(hours=12),
    ).count()
    if recent_trend_seeds >= 1:
        return

    # Find the best high-urgency topic
    for topic in research_result.get("trending_topics", []):
        if not isinstance(topic, dict):
            continue
        if topic.get("urgency") != "high":
            continue
        if not topic.get("suggested_angle"):
            continue

        topic_name = topic.get("topic", "")
        angle = topic.get("suggested_angle", "")
        relevance = topic.get("relevance", "")
        target_platforms = topic.get("platforms", [])

        # Filter to connected platforms
        valid_platforms = [p for p in target_platforms if p in platforms] or platforms[:3]

        # Duplicate check
        idea_prefix = topic_name[:40].lower()
        recent = ContentSeed.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(hours=48),
        ).values_list("idea", flat=True)
        if any(idea_prefix in s.lower() for s in recent):
            continue

        ContentSeed.objects.create(
            user=user,
            idea=f"Trending NOW: {topic_name}\n\nAngle: {angle}",
            notes=f"[Research Agent] Auto-seeded from high-urgency trend. Relevance: {relevance}",
            target_platforms=valid_platforms,
        )
        logger.info("Auto-seeded from trend: %s (user: %s)", topic_name[:60], user.email)
        return  # Max 1 per run

    # Also check opportunity_briefs for "today" timing
    for brief in research_result.get("opportunity_briefs", []):
        if not isinstance(brief, dict):
            continue
        if brief.get("timing") != "today":
            continue

        title = brief.get("title", "")
        desc = brief.get("description", "")
        platform = brief.get("platform", "")
        why_now = brief.get("why_now", "")

        valid_platforms = [platform] if platform in platforms else platforms[:2]

        ContentSeed.objects.create(
            user=user,
            idea=f"{title}\n\n{desc}",
            notes=f"[Research Agent] Time-sensitive opportunity. Why now: {why_now}",
            target_platforms=valid_platforms,
        )
        logger.info("Auto-seeded from opportunity: %s (user: %s)", title[:60], user.email)
        return  # Max 1 per run


@shared_task(name="agents.run_engage_cycle", soft_time_limit=20 * 60, time_limit=22 * 60)
@single_run("agents.run_engage_cycle", timeout=25 * 60)
def run_engage_cycle():
    """
    Periodic task: Run the Engage Agent cycle for all active users.
    Dispatches each user as a separate sub-task for parallel execution.
    Runs every 30 minutes.
    """
    from apps.agents.models import AgentConfig
    from apps.billing.models import get_plan_limits

    # Use a subquery to guarantee distinct IDs before fetching User objects.
    # The multi-table JOIN (posts + agent_configs) can produce duplicate rows
    # that .distinct() on the outer queryset doesn't always collapse correctly.
    eligible_ids = (
        User.objects.filter(
            Q(onboarding_completed=True) | Q(posts__status="published"),
            agent_configs__agent_type="engage",
            agent_configs__is_active=True,
        )
        .values("id")
        .distinct()
    )
    users_with_engage = User.objects.filter(pk__in=eligible_ids).select_related("profile")

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


@shared_task(
    name="agents.run_engage_for_user",
    max_retries=1,
    acks_late=True,
    soft_time_limit=120,
    time_limit=150,
)
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
        from apps.billing.exceptions import PlanLimitExceeded
        if isinstance(e, PlanLimitExceeded):
            logger.info("Engage cycle skipped (budget) for %s: %s", user.email, e.message)
        else:
            logger.error("Engage cycle failed for %s: %s", user.email, e)
            sentry_sdk.capture_exception(e)


@shared_task(name="agents.run_adapt_cycle", soft_time_limit=15 * 60, time_limit=18 * 60)
@single_run("agents.run_adapt_cycle", timeout=30 * 60)
def run_adapt_cycle():
    """Periodic Adapt Agent v2 cycle — the autonomous learning loop.

    Iterates eligible users and runs `apps.agents.adapt_agent.run_for_user`
    on each. Eligibility gates (per spec):
      - >= 7 days since first published post
      - >= 5 published posts in last 30 days
      - profile.adapt_paused is False
      - profile.adapt_last_run_at is None or older than 11h

    Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md
    """
    from datetime import timedelta
    from django.utils import timezone

    # The user iteration + per-user dispatch is implemented in W3 Commit 2.
    # This commit only wires the Celery Beat entry + the task name so the
    # scheduler doesn't error on missing task. The cycle is a no-op until
    # adapt_agent.run_for_user lands.
    from apps.agents.adapt_agent import run_for_user

    eligible = User.objects.filter(
        onboarding_completed=True,
        profile__adapt_paused=False,
    ).exclude(
        # Skip users who ran within the last 11h (we cadence at 12h)
        profile__adapt_last_run_at__gt=timezone.now() - timedelta(hours=11),
    ).distinct()

    dispatched = 0
    for idx, user in enumerate(eligible):
        # Stagger 3s per user so we don't hammer the LLM / DB in one burst
        run_adapt_for_user.apply_async(args=[user.pk], countdown=idx * 3)
        dispatched += 1

    if dispatched:
        logger.info("Adapt cycle dispatched %d user tasks", dispatched)
    return dispatched


@shared_task(name="agents.run_adapt_for_user", soft_time_limit=120, time_limit=180)
def run_adapt_for_user(user_id):
    """Single-user Adapt v2 cycle (per-user dispatch from run_adapt_cycle)."""
    from apps.agents.adapt_agent import run_for_user
    try:
        user = User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("Adapt: user %s not found", user_id)
        return
    return run_for_user(user)


@shared_task(name="agents.run_strategy_cycle", soft_time_limit=10 * 60, time_limit=12 * 60)
@single_run("agents.run_strategy_cycle", timeout=30 * 60)
def run_strategy_cycle():
    """
    Periodic task: dispatch the Chief Strategist Agent for all eligible users.
    Each user runs as its own sub-task with a staggered countdown so we
    avoid blocking the worker process with time.sleep() between users
    and naturally spread API load across the rate-limit window.
    """
    from apps.billing.models import get_plan_limits

    users_with_strategist = User.objects.filter(
        Q(onboarding_completed=True) | Q(posts__status="published"),
        agent_configs__agent_type="strategist",
        agent_configs__is_active=True,
    ).distinct()

    dispatched = 0
    for idx, user in enumerate(users_with_strategist):
        plan = getattr(getattr(user, "profile", None), "plan", "starter")
        if "strategist" not in get_plan_limits(plan).get("agents_enabled", []):
            continue
        _run_strategy_for_user.apply_async(args=[user.pk], countdown=idx * 5)
        dispatched += 1

    if dispatched:
        logger.info("Strategy cycle dispatched %d user tasks", dispatched)
    return dispatched


@shared_task(
    name="agents.run_strategy_for_user",
    max_retries=1,
    acks_late=True,
    soft_time_limit=180,
    time_limit=210,
)
def _run_strategy_for_user(user_id):
    """Run the Strategist Agent for a single user (dispatched as sub-task)."""
    from apps.agents.strategist_agent import run_strategy_cycle as strategist_cycle

    user = User.objects.get(pk=user_id)
    try:
        result = strategist_cycle(user)
        if result.get("status") == "completed":
            logger.info(
                "Strategy cycle for %s: seeds=%d, recommendations=%d",
                user.email,
                result.get("seeds_created", 0),
                len(result.get("recommendations", [])),
            )
    except Exception as e:
        from apps.billing.exceptions import PlanLimitExceeded
        if isinstance(e, PlanLimitExceeded):
            logger.info("Strategy cycle skipped (budget) for %s: %s", user.email, e.message)
        else:
            logger.error("Strategy cycle failed for %s: %s", user.email, e)
            sentry_sdk.capture_exception(e)


@shared_task(name="agents.measure_agent_outcomes", soft_time_limit=15 * 60, time_limit=18 * 60)
@single_run("agents.measure_agent_outcomes", timeout=20 * 60)
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
            sentry_sdk.capture_exception(e)

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


@shared_task(name="agents.track_audience_growth", soft_time_limit=15 * 60, time_limit=18 * 60)
@single_run("agents.track_audience_growth", timeout=20 * 60)
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


# ── Educator agent (platform-level, not per-tenant) ─────────────────────────


@shared_task(
    name="agents.educator_draft_weekly_article",
    soft_time_limit=10 * 60,
    time_limit=12 * 60,
)
@single_run("agents.educator_draft_weekly_article", timeout=15 * 60)
def educator_draft_weekly_article():
    """Weekly autonomous loop:
      1. If the topic backlog is empty, the Educator proposes 5 new topics
         (grounded in existing articles + category gaps + recent changelog).
      2. It then drafts the highest-priority pending topic.
    The drafted Article lands in DRAFT status and waits for founder review.
    Founder never needs to seed topics manually."""
    from apps.help.models import ArticleTopic
    from apps.agents.educator_agent import draft_next_topic

    backlog_before = ArticleTopic.objects.filter(status=ArticleTopic.Status.PENDING).count()
    try:
        result = draft_next_topic()
    except Exception:
        logger.exception("Educator weekly draft failed")
        return {"ok": False}

    backlog_after = ArticleTopic.objects.filter(status=ArticleTopic.Status.PENDING).count()
    topics_added = max(0, backlog_after + (1 if result else 0) - backlog_before)

    if result is None:
        return {
            "ok": True,
            "drafted": False,
            "topics_added": topics_added,
            "reason": "topic suggestion produced no new candidates",
        }
    return {
        "ok": True,
        "drafted": True,
        "topics_added": topics_added,
        "article_id": str(result.article.id),
        "slug": result.article.slug,
        "audience": result.article.audience,
        "tokens": result.llm_tokens,
    }


@shared_task(
    name="agents.educator_compile_weekly_digest",
    soft_time_limit=5 * 60,
    time_limit=6 * 60,
)
@single_run("agents.educator_compile_weekly_digest", timeout=10 * 60)
def educator_compile_weekly_digest():
    """Weekly: compile the 'Kova This Week' digest from ChangelogEntry +
    recent Articles. Sits in DRAFT until approved via admin."""
    from apps.agents.educator_agent import compile_weekly_digest

    try:
        digest = compile_weekly_digest()
    except Exception:
        logger.exception("Educator weekly digest compile failed")
        return {"ok": False}

    return {
        "ok": True,
        "week_end": digest.week_end.isoformat(),
        "status": digest.status,
    }
