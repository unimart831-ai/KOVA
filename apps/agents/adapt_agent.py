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
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "completed_at"])

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

    # Get cached optimal times or compute them
    timing = suggest_optimal_times(user)
    platform_times = timing.get("optimal_times", {}).get(platform, {})

    best_hours = platform_times.get("best_hours", [9, 12, 18])
    best_days = platform_times.get("best_days", [])

    now = timezone.now()

    # Find the next available optimal slot
    # Strategy: look ahead up to 7 days, find the first best_hour that's in the future
    for day_offset in range(7):
        candidate_date = now + timedelta(days=day_offset)
        day_name = candidate_date.strftime("%A")

        # If we have best_days data, prefer those days (but still schedule within 3 days)
        if best_days and day_name not in best_days and day_offset > 2:
            continue

        for hour in sorted(best_hours):
            candidate = candidate_date.replace(
                hour=hour, minute=0, second=0, microsecond=0
            )

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
                    "Auto-scheduled post %s for %s on %s",
                    post.id, platform, candidate.isoformat()
                )
                return candidate

    # Fallback: schedule for tomorrow at the first best hour
    tomorrow = now + timedelta(days=1)
    fallback_hour = best_hours[0] if best_hours else 9
    fallback = tomorrow.replace(
        hour=fallback_hour, minute=0, second=0, microsecond=0
    )
    post.scheduled_at = fallback
    post.save(update_fields=["scheduled_at"])
    return fallback
