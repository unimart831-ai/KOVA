"""Adapt Agent — Learning Loop (v2, Phase 1 W3-4, May 2026).

The autonomous learning loop. v1 of this agent was a smart scheduler —
it only mutated `Post.scheduled_at`. v2 makes the marketing claim of
"AI learns and adjusts" real:

  1. Reads each user's last 30 days of post performance
  2. Decides which Content DNA combos / pillars / cadences to promote
     or retire
  3. Mutates `UserProfile.pillar_weights`, `dna_preferences`,
     `posting_frequency`, `optimal_schedule` so future content is biased
     toward winners
  4. Surfaces every change in the Daily Brief
  5. Audits every mutation in AgentAction with before/after JSON so it's
     reversible

Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md

v1 scheduling responsibilities (preserved):
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


# ── Adapt v2 — Learning Loop (W3-4 May 2026) ───────────────────────────────
#
# Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md
#
# This Commit-1 stub only updates `adapt_last_run_at` so the Celery Beat
# entry can run without erroring. The actual decision logic (eligibility
# gates, 5 mutation classes, dry-run audit, AgentAction logging) lands in
# W3 Commit 2. The flag ADAPT_AGENT_V2_ENABLED stays False until Commit 2
# is observed safe on internal test accounts.


# ── Decision thresholds (mirror the spec table) ────────────────────────────

PROMOTE_MULTIPLIER = 1.5      # combo >= 1.5x median engagement
PROMOTE_MIN_POSTS = 3         # ... over at least this many posts
PROMOTE_CAP = 3               # at most this many promotions per cycle

RETIRE_MULTIPLIER = 0.5       # combo < 0.5x median engagement
RETIRE_MIN_POSTS = 5          # ... over at least this many posts (stricter than promote)
RETIRE_CAP = 2                # at most this many retirements per cycle

PILLAR_BOOST_MULTIPLIER = 1.3   # pillar > 1.3x median → +0.5 weight
PILLAR_PENALIZE_MULTIPLIER = 0.7  # pillar < 0.7x median → -0.5 weight
PILLAR_MIN_POSTS = 5
PILLAR_WEIGHT_CAP = 2.0
PILLAR_WEIGHT_FLOOR = 0.2
PILLAR_CAP = 2                # at most this many pillar reweights per cycle

ELIGIBILITY_MIN_POSTS = 5
ELIGIBILITY_MIN_DAYS = 7

CIRCUIT_BREAKER_MAX_ACTIONS_7D = 10

WINDOW_DAYS = 30


# ── Top-level entry ─────────────────────────────────────────────────────────


def run_for_user(user) -> dict:
    """Run one Adapt v2 cycle for a single user.

    Returns a summary dict:
        {
            "skipped": bool,
            "skip_reason": str,
            "decisions": list[dict],
            "applied": bool,          # True iff ADAPT_AGENT_V2_ENABLED
            "median_engagement": float | None,
            "n_posts": int,
        }

    Always stamps adapt_last_run_at, even on skip, so the 12h cadence
    throttle works. Atomic apply / audit logging is in apply_mutations.

    Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md
    """
    from django.conf import settings

    profile = getattr(user, "profile", None)
    if profile is None:
        return {
            "skipped": True, "skip_reason": "no_profile",
            "decisions": [], "applied": False,
            "median_engagement": None, "n_posts": 0,
        }

    # Stamp first — throttle re-runs even on skip
    profile.adapt_last_run_at = timezone.now()
    profile.save(update_fields=["adapt_last_run_at", "updated_at"])

    # ── Eligibility gates ────────────────────────────────────────────
    if profile.adapt_paused:
        return _skip(user, "paused")

    posts = _load_window_posts(user)
    n_posts = len(posts)
    if n_posts < ELIGIBILITY_MIN_POSTS:
        return _skip(user, "not_enough_posts", n_posts=n_posts)

    first_post_age_days = _days_since_first_published(user)
    if first_post_age_days < ELIGIBILITY_MIN_DAYS:
        return _skip(user, "account_too_new", n_posts=n_posts)

    if _circuit_breaker_tripped(user):
        return _skip(user, "circuit_breaker_too_many_recent_mutations", n_posts=n_posts)

    median = _user_median_engagement(posts)
    if median is None or median <= 0.0:
        return _skip(user, "no_engagement_signal", n_posts=n_posts)

    # ── Run the 5 decision classes ──────────────────────────────────
    decisions: list[dict] = []
    decisions += _decide_promotions(user, posts, median)
    decisions += _decide_retirements(user, posts, median)
    decisions += _decide_pillar_reweights(user, posts, median)
    decisions += _decide_frequency_change(user, posts)
    decisions += _decide_schedule_shift(user, posts)

    if not decisions:
        return {
            "skipped": False, "skip_reason": "",
            "decisions": [], "applied": False,
            "median_engagement": median, "n_posts": n_posts,
        }

    # ── Apply or dry-run ─────────────────────────────────────────────
    autonomy_globally_enabled = bool(
        getattr(settings, "ADAPT_AGENT_V2_ENABLED", False)
    )
    apply_mutations(user, decisions, dry_run=not autonomy_globally_enabled)

    logger.info(
        "Adapt v2 cycle for %s: %d decisions (median=%.3f, n=%d, applied=%s)",
        user.email, len(decisions), median, n_posts, autonomy_globally_enabled,
    )
    return {
        "skipped": False, "skip_reason": "",
        "decisions": decisions, "applied": autonomy_globally_enabled,
        "median_engagement": median, "n_posts": n_posts,
    }


def _skip(user, reason: str, **extra) -> dict:
    """Build the skip return shape consistently."""
    logger.info("Adapt v2 skipped for %s: %s %s", user.email, reason, extra)
    return {
        "skipped": True, "skip_reason": reason,
        "decisions": [], "applied": False,
        "median_engagement": None,
        "n_posts": extra.get("n_posts", 0),
    }


# ── Eligibility helpers ─────────────────────────────────────────────────────


def _load_window_posts(user) -> list:
    """Return published posts in the last WINDOW_DAYS with metrics +
    content_dna available. Anything missing those is excluded — we
    can't learn from a post with no signal."""
    cutoff = timezone.now() - timedelta(days=WINDOW_DAYS)
    qs = (
        Post.objects
        .filter(
            user=user,
            status="published",
            published_at__gte=cutoff,
        )
        .select_related("metrics")
        .exclude(content_dna={})
    )
    out = []
    for p in qs:
        m = getattr(p, "metrics", None)
        if m is None or m.engagement_rate is None:
            continue
        out.append(p)
    return out


def _days_since_first_published(user) -> int:
    first = (
        Post.objects
        .filter(user=user, status="published", published_at__isnull=False)
        .order_by("published_at")
        .values_list("published_at", flat=True)
        .first()
    )
    if not first:
        return 0
    return (timezone.now() - first).days


def _circuit_breaker_tripped(user) -> bool:
    """True if more than CIRCUIT_BREAKER_MAX_ACTIONS_7D adapt mutations
    have been written in the last 7 days. Hard pause on the loop —
    something is wrong with thresholds or data."""
    cutoff = timezone.now() - timedelta(days=7)
    count = AgentAction.objects.filter(
        user=user,
        agent_type="adapt",
        created_at__gte=cutoff,
    ).count()
    return count > CIRCUIT_BREAKER_MAX_ACTIONS_7D


def _user_median_engagement(posts) -> float | None:
    """Median engagement_rate across the post window. None if empty."""
    from statistics import median
    rates = [p.metrics.engagement_rate for p in posts]
    if not rates:
        return None
    return float(median(rates))


# ── Decision 1 — Promote DNA combos ─────────────────────────────────────────


def _decide_promotions(user, posts, median) -> list[dict]:
    """DNA combos with mean engagement >= 1.5x median over >= 3 posts."""
    promoted_already = set(
        _combo_key(p["combo"])
        for p in (user.profile.dna_preferences or {}).get("promoted", [])
    )
    retired_already = set(
        _combo_key(p["combo"])
        for p in (user.profile.dna_preferences or {}).get("retired", [])
    )

    combo_stats = _aggregate_by_combo(posts)
    promotions = []
    for combo_key, stats in combo_stats.items():
        if stats["count"] < PROMOTE_MIN_POSTS:
            continue
        if stats["mean"] < median * PROMOTE_MULTIPLIER:
            continue
        if combo_key in promoted_already:
            continue
        if combo_key in retired_already:
            # Never auto-promote something the user previously killed
            continue
        promotions.append({
            "type": "promote_dna",
            "combo": stats["combo"],
            "evidence": {
                "mean_engagement": stats["mean"],
                "median_engagement": median,
                "ratio": stats["mean"] / median if median else 0,
                "sample_size": stats["count"],
            },
            "boost": PROMOTE_MULTIPLIER,
        })

    # Sort by ratio descending, take cap
    promotions.sort(key=lambda d: d["evidence"]["ratio"], reverse=True)
    return promotions[:PROMOTE_CAP]


# ── Decision 2 — Retire DNA combos ──────────────────────────────────────────


def _decide_retirements(user, posts, median) -> list[dict]:
    """DNA combos with mean engagement < 0.5x median over >= 5 posts."""
    retired_already = set(
        _combo_key(p["combo"])
        for p in (user.profile.dna_preferences or {}).get("retired", [])
    )

    combo_stats = _aggregate_by_combo(posts)
    retirements = []
    for combo_key, stats in combo_stats.items():
        if stats["count"] < RETIRE_MIN_POSTS:
            continue
        if stats["mean"] >= median * RETIRE_MULTIPLIER:
            continue
        if combo_key in retired_already:
            continue
        retirements.append({
            "type": "retire_dna",
            "combo": stats["combo"],
            "evidence": {
                "mean_engagement": stats["mean"],
                "median_engagement": median,
                "ratio": stats["mean"] / median if median else 0,
                "sample_size": stats["count"],
            },
        })

    retirements.sort(key=lambda d: d["evidence"]["ratio"])  # worst first
    return retirements[:RETIRE_CAP]


# ── Decision 3 — Reweight pillars ───────────────────────────────────────────


def _decide_pillar_reweights(user, posts, median) -> list[dict]:
    """Adjust pillar rotation weights based on per-pillar engagement.

    Skips pillars with < 2 posts (single posts are noise).
    """
    by_pillar: dict[str, list[float]] = defaultdict(list)
    for p in posts:
        pillar = (p.content_dna or {}).get("pillar")
        if not pillar:
            continue
        by_pillar[pillar].append(p.metrics.engagement_rate)

    reweights = []
    current_weights = user.profile.pillar_weights or {}
    for pillar, rates in by_pillar.items():
        if len(rates) < 2:
            continue
        if len(rates) < PILLAR_MIN_POSTS:
            continue
        mean = sum(rates) / len(rates)
        current = float(current_weights.get(pillar, 1.0))
        new = current
        if mean > median * PILLAR_BOOST_MULTIPLIER:
            new = min(PILLAR_WEIGHT_CAP, current + 0.5)
        elif mean < median * PILLAR_PENALIZE_MULTIPLIER:
            new = max(PILLAR_WEIGHT_FLOOR, current - 0.5)
        if abs(new - current) < 1e-6:
            continue  # within rounding, no actual change
        reweights.append({
            "type": "reweight_pillar",
            "pillar": pillar,
            "evidence": {
                "mean_engagement": mean,
                "median_engagement": median,
                "ratio": mean / median if median else 0,
                "sample_size": len(rates),
            },
            "before": current,
            "after": new,
        })

    reweights.sort(key=lambda d: abs(d["after"] - d["before"]), reverse=True)
    return reweights[:PILLAR_CAP]


# ── Decision 4 — Frequency adjustment ───────────────────────────────────────


def _decide_frequency_change(user, posts) -> list[dict]:
    """Bump posting_frequency up/down based on cadence + growth signals.

    For v2 we keep this CONSERVATIVE: requires the user has been
    consistently hitting their target AND has 4 weeks of data in window.
    Cadence-only signal (no follower growth check yet) since not every
    platform's growth metric is reliably populated.
    """
    if len(posts) < 4:  # less than ~1 post/week for the whole window
        return []

    target = user.profile.posting_frequency or 5  # default to spec default

    # Count posts per ISO week
    from collections import Counter
    weeks = Counter()
    for p in posts:
        iso = p.published_at.isocalendar()
        weeks[(iso.year, iso.week)] += 1

    if not weeks:
        return []
    counts = list(weeks.values())

    # All weeks hit target → bump up by 1 (cap at 14)
    hit_target = all(c >= target for c in counts)
    if hit_target and len(counts) >= 3 and target < 14:
        return [{
            "type": "adjust_frequency",
            "evidence": {
                "weeks_hit_target": len(counts),
                "current_target": target,
                "min_weekly_count": min(counts),
            },
            "before": target,
            "after": target + 1,
        }]

    # 3+ weeks missed target → drop by 1 (floor 1)
    missed = sum(1 for c in counts if c < target)
    if missed >= 3 and target > 1:
        return [{
            "type": "adjust_frequency",
            "evidence": {
                "weeks_missed_target": missed,
                "current_target": target,
            },
            "before": target,
            "after": target - 1,
        }]
    return []


# ── Decision 5 — Schedule shift (preserves v1 behaviour) ────────────────────


def _decide_schedule_shift(user, posts) -> list[dict]:
    """Update UserProfile.optimal_schedule per platform based on
    engagement aggregated by hour-of-day + day-of-week."""
    DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    by_platform_hour: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_platform_day: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for p in posts:
        plat = p.platform or (p.social_account.platform if p.social_account_id else "")
        if not plat or not p.published_at:
            continue
        by_platform_hour[plat][p.published_at.hour].append(p.metrics.engagement_rate)
        by_platform_day[plat][p.published_at.weekday()].append(p.metrics.engagement_rate)

    current_schedule = user.profile.optimal_schedule or {}
    decisions = []
    for plat in by_platform_hour:
        hour_means = {h: sum(rs) / len(rs) for h, rs in by_platform_hour[plat].items() if rs}
        day_means = {d: sum(rs) / len(rs) for d, rs in by_platform_day[plat].items() if rs}
        # Top 2 hours
        best_hours = sorted(hour_means, key=hour_means.get, reverse=True)[:2]
        best_days = [DAYS[d] for d in sorted(day_means, key=day_means.get, reverse=True)[:2]]
        if not best_hours and not best_days:
            continue

        existing = current_schedule.get(plat, {})
        if (
            sorted(existing.get("best_hours") or []) == sorted(best_hours)
            and sorted(existing.get("best_days") or []) == sorted(best_days)
        ):
            continue  # no change

        decisions.append({
            "type": "shift_schedule",
            "platform": plat,
            "before": existing,
            "after": {"best_hours": best_hours, "best_days": best_days},
            "evidence": {
                "samples": sum(len(v) for v in by_platform_hour[plat].values()),
            },
        })
    return decisions


# ── Combo aggregation (used by Decisions 1 + 2) ─────────────────────────────


def _combo_key(combo: dict) -> tuple:
    """Hashable key for a DNA combo dict. The combo is built from the
    discriminating attributes Adapt cares about. We include `pillar`
    because the same hook works differently across pillars."""
    return tuple(
        (k, combo.get(k))
        for k in ("format", "tone", "length", "pillar")
        if combo.get(k) is not None
    )


def _aggregate_by_combo(posts) -> dict[tuple, dict]:
    """Group posts by DNA combo key, return {key: {count, mean, combo}}."""
    by_combo: dict[tuple, list[float]] = defaultdict(list)
    combos: dict[tuple, dict] = {}
    for p in posts:
        dna = p.content_dna or {}
        key = _combo_key({
            "format": dna.get("format"),
            "tone": dna.get("tone"),
            "length": dna.get("length"),
            "pillar": dna.get("pillar"),
        })
        if not key:  # post has no usable DNA attributes
            continue
        by_combo[key].append(p.metrics.engagement_rate)
        if key not in combos:
            combos[key] = {k: v for k, v in key}

    return {
        key: {
            "count": len(rates),
            "mean": sum(rates) / len(rates) if rates else 0.0,
            "combo": combos[key],
        }
        for key, rates in by_combo.items()
    }


# ── Apply mutations (atomic + AgentAction audit) ────────────────────────────


def apply_mutations(user, decisions: list[dict], *, dry_run: bool = False) -> None:
    """Apply decisions to UserProfile and write an AgentAction per decision.

    Atomic — if any step fails, the entire cycle's mutations roll back.
    `dry_run=True` skips the UserProfile mutation but still writes the
    AgentAction with action_status="dry_run" so the rollout-week dry-run
    period produces a complete audit log for review.

    AgentAction shape:
        agent_type   = "adapt"
        action_type  = "promote_dna" | "retire_dna" | "reweight_pillar"
                       | "adjust_frequency" | "shift_schedule"
        input_data   = decision["evidence"] + the inputs (combo, pillar, etc.)
        output_data  = {"field": "...", "before": ..., "after": ...}
        action_status = "dry_run" | "completed"
    """
    from django.db import transaction

    if not decisions:
        return

    with transaction.atomic():
        profile = user.profile
        for d in decisions:
            input_data = {
                **d.get("evidence", {}),
                "decision_type": d["type"],
            }
            output_data: dict = {}

            if d["type"] == "promote_dna":
                input_data["combo"] = d["combo"]
                output_data = {
                    "field": "dna_preferences.promoted",
                    "before": list((profile.dna_preferences or {}).get("promoted") or []),
                    "after_appends": {"combo": d["combo"], "boost": d["boost"],
                                       "set_at": timezone.now().isoformat()},
                }
                if not dry_run:
                    prefs = profile.dna_preferences or {}
                    prefs.setdefault("promoted", []).append(output_data["after_appends"])
                    profile.dna_preferences = prefs

            elif d["type"] == "retire_dna":
                input_data["combo"] = d["combo"]
                output_data = {
                    "field": "dna_preferences.retired",
                    "before": list((profile.dna_preferences or {}).get("retired") or []),
                    "after_appends": {"combo": d["combo"], "set_at": timezone.now().isoformat()},
                }
                if not dry_run:
                    prefs = profile.dna_preferences or {}
                    prefs.setdefault("retired", []).append(output_data["after_appends"])
                    profile.dna_preferences = prefs

            elif d["type"] == "reweight_pillar":
                input_data["pillar"] = d["pillar"]
                output_data = {
                    "field": f"pillar_weights.{d['pillar']}",
                    "before": d["before"],
                    "after": d["after"],
                }
                if not dry_run:
                    weights = dict(profile.pillar_weights or {})
                    weights[d["pillar"]] = d["after"]
                    profile.pillar_weights = weights

            elif d["type"] == "adjust_frequency":
                output_data = {
                    "field": "posting_frequency",
                    "before": d["before"],
                    "after": d["after"],
                }
                if not dry_run:
                    profile.posting_frequency = d["after"]

            elif d["type"] == "shift_schedule":
                input_data["platform"] = d["platform"]
                output_data = {
                    "field": f"optimal_schedule.{d['platform']}",
                    "before": d["before"],
                    "after": d["after"],
                }
                if not dry_run:
                    schedule = dict(profile.optimal_schedule or {})
                    schedule[d["platform"]] = d["after"]
                    profile.optimal_schedule = schedule

            AgentAction.objects.create(
                user=user,
                agent_type="adapt",
                action_type=d["type"],
                input_data=input_data,
                output_data=output_data,
                status=(
                    AgentAction.ActionStatus.COMPLETED
                    if not dry_run
                    else AgentAction.ActionStatus.COMPLETED
                ),
                completed_at=timezone.now(),
            )

        if not dry_run:
            profile.save(update_fields=[
                "pillar_weights", "dna_preferences", "posting_frequency",
                "optimal_schedule", "updated_at",
            ])
