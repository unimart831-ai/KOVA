"""
Adapt Agent — Smart Scheduling & Platform Optimization.

Responsibilities:
  1. Analyze historical posting performance by time-of-day / day-of-week
  2. Suggest optimal posting times per platform
  3. Auto-schedule posts to optimal slots
  4. Adapt content timing based on audience activity patterns
"""

import json
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, F
from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.agents.models import AgentAction, AgentConfig
from apps.analytics.models import PostMetric
from apps.content.models import Post

logger = logging.getLogger(__name__)


# ── Platform-specific scheduling defaults ────────────────────────────────────
# Used when a user has no historical engagement data (new accounts).
# Based on aggregated industry research for each platform's peak audience
# activity windows. All hours in 24h format (local time, converted to UTC
# at schedule time using the user's timezone setting).
#
# Facebook: Business/community content performs best mid-morning and early
#   afternoon on weekdays. Wednesday is consistently the top day.
# Instagram: Audience peaks during commute (7AM), lunch (12PM), and evening
#   wind-down (19PM). Strong Mon-Fri with Saturday performing well for lifestyle.
# Twitter/X: Morning commute and lunch dominate. Fast-moving — early posting
#   in the window matters more than day-of-week.
# LinkedIn: Business hours only. Tuesday/Wednesday/Thursday are the power days.
#   Avoid weekends — engagement drops 70-80%.
# TikTok: Evening and night. Audience skews younger and is most active post-work.
# YouTube: Late afternoon and early evening — people watch after school/work.
#   Weekends are strong for long-form content.
# Pinterest: Evenings and weekends. High Saturday engagement for lifestyle/DIY.
# Threads/Bluesky: Similar to Twitter — morning and midday on weekdays.

_PLATFORM_SCHEDULING_DEFAULTS: dict[str, dict] = {
    "facebook": {
        "best_hours": [9, 13, 15],
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
    },
    "instagram": {
        "best_hours": [7, 12, 19],
        "best_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    },
    "twitter": {
        "best_hours": [8, 12, 17],
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
    },
    "linkedin": {
        "best_hours": [8, 10, 12],
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
    },
    "tiktok": {
        "best_hours": [19, 20, 21],
        "best_days": [],  # TikTok is 7-day consistent
    },
    "youtube": {
        "best_hours": [15, 17, 20],
        "best_days": ["Friday", "Saturday", "Sunday"],
    },
    "pinterest": {
        "best_hours": [20, 21, 14],
        "best_days": ["Saturday", "Sunday", "Friday"],
    },
    "threads": {
        "best_hours": [8, 12, 17],
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
    },
    "bluesky": {
        "best_hours": [9, 12, 16],
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
    },
    "whatsapp": {
        "best_hours": [9, 13, 18],
        "best_days": [],
    },
}


def _analyze_time_performance(user, days=30):
    """
    Analyze engagement rates by hour-of-day and day-of-week
    for each platform the user publishes on.
    """
    cutoff = timezone.now() - timedelta(days=days)

    posts = (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            published_at__gte=cutoff,
            published_at__isnull=False,
        )
        .select_related("social_account", "metrics")
        .order_by("-published_at")
    )

    platform_data = defaultdict(lambda: {
        "hourly": defaultdict(lambda: {"total_engagement": 0, "count": 0}),
        "daily": defaultdict(lambda: {"total_engagement": 0, "count": 0}),
        "posts_analyzed": 0,
    })

    for post in posts:
        platform = post.social_account.platform if post.social_account else "unknown"

        try:
            engagement = post.metrics.engagement_rate or 0
        except PostMetric.DoesNotExist:
            continue

        hour = post.published_at.hour
        day = post.published_at.strftime("%A")

        platform_data[platform]["hourly"][hour]["total_engagement"] += engagement
        platform_data[platform]["hourly"][hour]["count"] += 1
        platform_data[platform]["daily"][day]["total_engagement"] += engagement
        platform_data[platform]["daily"][day]["count"] += 1
        platform_data[platform]["posts_analyzed"] += 1

    # Calculate averages
    results = {}
    for platform, data in platform_data.items():
        hourly_avg = {}
        for hour, stats in data["hourly"].items():
            if stats["count"] > 0:
                hourly_avg[hour] = round(stats["total_engagement"] / stats["count"], 2)

        daily_avg = {}
        for day, stats in data["daily"].items():
            if stats["count"] > 0:
                daily_avg[day] = round(stats["total_engagement"] / stats["count"], 2)

        results[platform] = {
            "hourly_engagement": hourly_avg,
            "daily_engagement": daily_avg,
            "posts_analyzed": data["posts_analyzed"],
        }

    return results


def suggest_optimal_times(user):
    """
    Adapt Agent: Analyze posting patterns and suggest optimal times
    for each connected platform.

    Returns a dict with optimal_times per platform and reasoning.
    """
    config = AgentConfig.objects.filter(
        user=user, agent_type="adapt"
    ).first()
    if config and not config.is_active:
        logger.info("Adapt agent disabled for %s, skipping", user.email)
        return {"optimal_times": {}, "has_data": False}

    action = AgentAction.objects.create(
        user=user,
        agent_type="adapt",
        action_type="suggest_optimal_times",
        description="Analyzing audience activity patterns for optimal posting times",
    )

    try:
        time_data = _analyze_time_performance(user, days=30)

        if not time_data:
            action.status = AgentAction.ActionStatus.COMPLETED
            action.output_data = {"message": "No published posts to analyze timing"}
            action.save(update_fields=["status", "output_data"])
            return {
                "optimal_times": {},
                "has_data": False,
                "message": "Publish more content to unlock smart scheduling. Need at least a few posts with engagement data.",
            }

        # Get user's timezone preference
        user_tz = user.timezone or "UTC"

        system_prompt = (
            "You are a social media scheduling optimizer. Based on historical engagement data, "
            "recommend the optimal posting times for each platform.\n\n"
            "Consider:\n"
            "- Which hours consistently get higher engagement\n"
            "- Which days of the week perform best\n"
            "- Platform-specific audience behavior patterns\n"
            "- Common knowledge about platform peak times as a baseline\n\n"
            f"User's timezone: {user_tz}\n\n"
            "Respond in JSON with key 'optimal_times', a dict where each key is a platform name:\n"
            '  - "best_hours": list of 3 optimal hours (24h format, e.g. [9, 12, 18])\n'
            '  - "best_days": list of 2-3 best days of the week\n'
            '  - "avoid_hours": list of hours to avoid\n'
            '  - "reasoning": 1-2 sentences explaining the recommendation\n'
            '  - "confidence": "high" | "medium" | "low" based on data volume\n'
        )

        prompt = (
            f"Here is the historical engagement data by posting time:\n\n"
            f"{json.dumps(time_data, indent=2, default=str)}\n\n"
            "Recommend optimal posting times for each platform."
        )

        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("adapt.schedule"),
            json_mode=True,
            temperature=0.3,
            max_tokens=1200,
        )

        try:
            result = parse_llm_json(response.content)
        except (json.JSONDecodeError, ValueError):
            result = {"optimal_times": {}, "raw": response.content}

        result["has_data"] = True

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = result
        action.tokens_used = response.total_tokens
        action.input_tokens = response.input_tokens
        action.output_tokens = response.output_tokens
        action.model_used = response.model
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "input_tokens", "output_tokens", "model_used", "completed_at"])

        return result

    except Exception as e:
        logger.exception("Adapt Agent timing analysis failed: %s", e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return {"optimal_times": {}, "has_data": False}


def auto_schedule_post(post):
    """
    Automatically assign an optimal scheduled_at time to a post
    based on the Adapt Agent's analysis of the user's audience patterns.

    Called after content generation when auto_approve is on, or when
    user approves a post without setting a specific time.

    Returns the assigned datetime or None if scheduling isn't possible.
    """
    user = post.user

    # Only schedule posts that don't already have a time
    if post.scheduled_at:
        return post.scheduled_at

    platform = post.social_account.platform if post.social_account else None
    if not platform:
        return None

    # ── Respect posting_frequency: check weekly budget ──
    profile = getattr(user, "profile", None)
    posting_frequency = getattr(profile, "posting_frequency", 5) or 5

    week_start = timezone.now() - timedelta(days=7)
    posts_this_week = Post.objects.filter(
        user=user,
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED, Post.Status.PUBLISHED],
        scheduled_at__gte=week_start,
    ).count()

    if posts_this_week >= posting_frequency:
        logger.info(
            "Weekly posting limit reached for %s (%d/%d). Skipping auto-schedule for post %s.",
            user.email, posts_this_week, posting_frequency, post.id,
        )
        return None

    # Get cached optimal times or compute them
    timing = suggest_optimal_times(user)
    platform_times = timing.get("optimal_times", {}).get(platform, {})

    # Use platform-specific industry defaults when no user history exists yet.
    # These are research-backed peak windows per platform, not generic 9/12/18.
    platform_defaults = _PLATFORM_SCHEDULING_DEFAULTS.get(
        platform, {"best_hours": [9, 12, 18], "best_days": []}
    )
    best_hours = platform_times.get("best_hours") or platform_defaults["best_hours"]
    best_days = platform_times.get("best_days") or platform_defaults["best_days"]

    now = timezone.now()

    # ── Convert best_hours to user's timezone for accurate scheduling ──
    import zoneinfo
    user_tz_name = user.timezone or "UTC"
    try:
        user_tz = zoneinfo.ZoneInfo(user_tz_name)
    except (KeyError, Exception):
        user_tz = zoneinfo.ZoneInfo("UTC")

    # Find the next available optimal slot
    # Strategy: look ahead up to 7 days, find the first best_hour that's in the future
    for day_offset in range(7):
        candidate_date = now + timedelta(days=day_offset)
        day_name = candidate_date.strftime("%A")

        # If we have best_days data, prefer those days (but still schedule within 3 days)
        if best_days and day_name not in best_days and day_offset > 2:
            continue

        for hour in sorted(best_hours):
            # Build candidate in user's timezone, then convert to UTC for storage
            from datetime import datetime as dt
            local_candidate = candidate_date.astimezone(user_tz).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            # Convert back to UTC-aware datetime
            candidate = local_candidate.astimezone(zoneinfo.ZoneInfo("UTC"))

            # Must be in the future (at least 30 min from now)
            if candidate <= now + timedelta(minutes=30):
                continue

            # Check no other post is already scheduled at this exact time for this platform
            conflict = Post.objects.filter(
                user=user,
                social_account=post.social_account,
                scheduled_at=candidate,
                status__in=[
                    Post.Status.APPROVED,
                    Post.Status.SCHEDULED,
                ],
            ).exists()

            if not conflict:
                post.scheduled_at = candidate
                post.save(update_fields=["scheduled_at"])
                logger.info(
                    "Auto-scheduled post %s for %s at %s (user TZ: %s)",
                    post.id, platform, candidate.isoformat(), user_tz_name,
                )
                return candidate

    # Fallback: schedule for tomorrow at the first best hour (in user's timezone)
    tomorrow = now + timedelta(days=1)
    fallback_hour = best_hours[0] if best_hours else 9
    local_fallback = tomorrow.astimezone(user_tz).replace(
        hour=fallback_hour, minute=0, second=0, microsecond=0
    )
    fallback = local_fallback.astimezone(zoneinfo.ZoneInfo("UTC"))
    post.scheduled_at = fallback
    post.save(update_fields=["scheduled_at"])
    return fallback
