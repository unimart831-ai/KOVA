"""
Daily Brief Generation — Celery tasks for the Chief Strategist Agent.

Generates a personalized daily brief for each user at their preferred time.
Pulls data from: Analyst Agent, Content pipeline, Agent activity log.
"""

import json
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.agents.analyst_agent import analyze_performance, get_content_dna_summary
from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.agents.models import AgentAction, AgentConfig
from apps.agents.strategist_agent import get_engagement_report, run_strategy_cycle
from apps.analytics.competitor_intel import get_competitor_context_for_brief
from apps.billing.models import get_plan_limits
from apps.briefs.models import DailyBrief
from apps.content.models import ContentSeed, Post
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)
User = get_user_model()


def _send_brief_email(user, brief):
    """Send the daily brief via email if the user's plan includes email briefs."""
    profile = getattr(user, "profile", None)
    if not profile:
        return

    limits = get_plan_limits(profile.plan)
    if not limits.get("email_brief"):
        return  # Plan doesn't include email briefs

    try:
        from apps.emails.services import email_service
        email_service._send(
            email_type="daily_brief",
            to_email=user.email,
            context={
                "first_name": user.first_name,
                "user": user,
                "brief": brief,
                "site_url": settings.SITE_URL if hasattr(settings, "SITE_URL") else "",
            },
            user=user,
            subject=f"Your Daily Brief — {brief.date.strftime('%b %d, %Y')}",
        )
        logger.info("Email brief sent to %s", user.email)
    except Exception as e:
        logger.warning("Failed to send email brief to %s: %s", user.email, e)


def _gather_brief_data(user):
    """Collect all data needed for the daily brief."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    # Yesterday's published posts
    yesterday_posts = Post.objects.filter(
        user=user,
        status=Post.Status.PUBLISHED,
        published_at__date=yesterday,
    ).select_related("social_account")

    # Pending posts needing approval
    pending_posts = Post.objects.filter(
        user=user,
        status=Post.Status.PENDING_APPROVAL,
    ).count()

    # Scheduled posts for today
    scheduled_today = Post.objects.filter(
        user=user,
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
        scheduled_at__date=today,
    ).count()

    # Failed posts
    failed_posts = Post.objects.filter(
        user=user,
        status=Post.Status.FAILED,
    ).count()

    # Recent agent activity (last 24 hours)
    recent_actions = AgentAction.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).values("agent_type", "action_type", "status").order_by("-created_at")[:20]

    # Performance analysis from Analyst Agent
    try:
        perf = analyze_performance(user, days=7)
    except Exception as e:
        logger.warning("Performance analysis failed: %s", e)
        perf = {"summary": "Performance data unavailable.", "performance_data": {}}

    # Content DNA summary
    try:
        dna_summary = get_content_dna_summary(user, days=30)
    except Exception as e:
        logger.warning("Content DNA summary failed: %s", e)
        dna_summary = {"winning_attributes": [], "total_analyzed": 0}

    # Trend research — use cached Research Agent results (avoid live LLM call)
    try:
        from apps.agents.models import AgentAction as _AA
        latest_research = (
            _AA.objects.filter(
                user=user,
                agent_type="research",
                action_type="discover_trends",
                status=_AA.ActionStatus.COMPLETED,
            )
            .order_by("-created_at")
            .values_list("output_data", flat=True)
            .first()
        )
        trends = latest_research or {"trending_topics": [], "opportunity_briefs": []}
    except Exception as e:
        logger.warning("Trend data retrieval failed: %s", e)
        trends = {"trending_topics": [], "opportunity_briefs": []}

    # Engagement report from Strategist Agent
    try:
        engagement = get_engagement_report(user, days=7)
    except Exception as e:
        logger.warning("Engagement report failed: %s", e)
        engagement = {"total_interactions": 0, "summary": "Engagement data unavailable."}

    # Competitor intelligence
    try:
        competitor_intel = get_competitor_context_for_brief(user)
    except Exception as e:
        logger.warning("Competitor intel for brief failed: %s", e)
        competitor_intel = {}

    # Posts created this week
    week_stats = Post.objects.filter(
        user=user,
        created_at__date__gte=week_ago,
    ).aggregate(
        total_created=Count("id"),
        published=Count("id", filter=Q(status=Post.Status.PUBLISHED)),
        failed=Count("id", filter=Q(status=Post.Status.FAILED)),
    )

    return {
        "today": today.isoformat(),
        "yesterday_published": yesterday_posts.count(),
        "yesterday_posts_summary": [
            {
                "platform": p.social_account.platform if p.social_account else "unknown",
                "content_preview": p.content_text[:80],
                "engagement": getattr(getattr(p, "metrics", None), "engagement_rate", None),
            }
            for p in yesterday_posts[:10]
        ],
        "pending_approval": pending_posts,
        "scheduled_today": scheduled_today,
        "failed_posts": failed_posts,
        "week_stats": week_stats,
        "agent_activity": list(recent_actions),
        "performance": perf,
        "content_dna": dna_summary,
        "trends": trends,
        "engagement": engagement,
        "competitor_intel": competitor_intel,
    }


def _generate_brief_with_llm(user, brief_data):
    """Use LLM to compose a natural-language daily brief."""
    profile = getattr(user, "profile", None)
    company = getattr(profile, "company_name", "") if profile else ""

    system_prompt = (
        "You are the Chief Strategist Agent for Kova Agent, an AI social media platform. "
        "You compile a daily brief for the user — a concise, actionable morning summary. "
        f"The user's brand is '{company}'. "
        "Write in a warm but professional tone, like a smart assistant who knows the business.\n\n"
        "Respond in JSON with these keys:\n"
        '- "summary": 3-5 sentences — the main briefing (what happened, what needs attention, what\'s coming)\n'
        '- "trending_topics": list of 3-5 relevant trending topics/hashtags to consider for content today\n'
        '- "suggested_posts": list of 2-3 content ideas with {idea, reasoning, platform} — based on what\'s working\n'
        '- "performance_highlight": one standout metric or insight from yesterday\n'
        '- "engagement_summary": 2-3 sentences about engagement health — response rate, sentiment trends, '
        'superfans to acknowledge, unanswered items needing attention\n'
        '- "agent_summary": 1-2 sentences about what the AI agents did in the last 24 hours\n'
        '- "competitor_update": 1-2 sentences about competitor activity — new insights, '
        'content gaps to exploit, or threats to watch. Empty string if no competitor data.\n'
    )

    prompt = (
        f"Compile today's daily brief based on this data:\n\n"
        f"{json.dumps(brief_data, indent=2, default=str)}\n\n"
        "Generate an actionable, personalized daily brief."
    )

    response = generate(
        prompt=prompt,
        system=system_prompt,
        model=get_model_for_task("strategist.brief", user=user),
        json_mode=True,
        temperature=0.4,
        max_tokens=1500,
    )
    return response


def generate_daily_brief(user):
    """Generate a daily brief for a single user. Called by the periodic task."""
    today = timezone.now().date()

    # Don't regenerate if already exists
    if DailyBrief.objects.filter(user=user, date=today).exists():
        logger.info("Brief already exists for %s on %s", user.email, today)
        return None

    # Check if strategist agent is active
    strategist_active = AgentConfig.objects.filter(
        user=user, agent_type="strategist", is_active=True
    ).exists()

    if not strategist_active:
        # Auto-create if missing (same pattern as agent_control view)
        config, _ = AgentConfig.objects.get_or_create(
            user=user, agent_type="strategist",
        )
        if not config.is_active:
            logger.info("Strategist agent disabled for %s, skipping brief", user.email)
            return None

    action = AgentAction.objects.create(
        user=user,
        agent_type="strategist",
        action_type="generate_daily_brief",
        description=f"Generating daily brief for {today}",
    )

    try:
        brief_data = _gather_brief_data(user)
        response = _generate_brief_with_llm(user, brief_data)

        try:
            llm_result = parse_llm_json(response.content)
        except (json.JSONDecodeError, ValueError):
            llm_result = {
                "summary": response.content[:1000] if "{" not in response.content[:5] else "Your daily brief is ready.",
                "trending_topics": [],
                "suggested_posts": [],
                "performance_highlight": "",
                "agent_summary": "",
            }

        # Merge LLM trending topics with Research Agent's richer trend data
        research_trends = brief_data.get("trends", {})
        raw_topics = llm_result.get("trending_topics", [])
        research_topics = research_trends.get("trending_topics", [])

        # Prefer Research Agent's structured topics, fall back to LLM's list
        if research_topics:
            trending_topics = research_topics
        elif raw_topics:
            # Normalize simple strings into dicts
            trending_topics = [
                {"topic": t} if isinstance(t, str) else t
                for t in raw_topics
            ]
        else:
            trending_topics = []

        # Merge suggested posts: LLM ideas + Research Agent opportunity briefs
        llm_suggestions = llm_result.get("suggested_posts", [])
        opportunity_briefs = research_trends.get("opportunity_briefs", [])
        suggested_posts = llm_suggestions + [
            {
                "idea": ob.get("title", ""),
                "reasoning": ob.get("description", ""),
                "platform": ob.get("platform", ""),
                "timing": ob.get("timing", ""),
                "content_type": ob.get("content_type", ""),
            }
            for ob in opportunity_briefs
            if ob.get("title")
        ]

        brief = DailyBrief.objects.create(
            user=user,
            date=today,
            summary=llm_result.get("summary", "Your daily brief is ready."),
            trending_topics=trending_topics,
            suggested_posts=suggested_posts,
            performance_summary={
                "highlight": llm_result.get("performance_highlight", ""),
                "agent_summary": llm_result.get("agent_summary", ""),
                "data": brief_data.get("performance", {}).get("performance_data", {}),
            },
            agent_activity=[
                {"type": a["agent_type"], "action": a["action_type"], "status": a["status"]}
                for a in brief_data.get("agent_activity", [])
            ],
            posts_pending=brief_data["pending_approval"],
        )

        # Create notification
        Notification.create_for_user(
            user=user,
            notification_type="system",
            message="Your daily brief is ready. Good morning!",
        )

        # Send email brief (if plan includes it)
        _send_brief_email(user, brief)

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {"brief_id": str(brief.id)}
        action.tokens_used = response.total_tokens
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "completed_at"])

        logger.info("Daily brief generated for %s", user.email)
        return brief

    except Exception as e:
        logger.exception("Daily brief generation failed for %s: %s", user.email, e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return None


@shared_task(name="briefs.generate_all_daily_briefs")
def generate_all_daily_briefs():
    """
    Periodic task: Generate daily briefs for all users whose brief time has passed.
    Runs every 15 minutes. Checks each user's daily_brief_time in THEIR timezone.
    """
    import zoneinfo

    now_utc = timezone.now()

    # Find users who MIGHT need a brief (haven't got one today, are active).
    # We check the time condition per-user below because each user has their
    # own timezone — we can't filter by a single UTC cutoff.
    candidates = list(
        User.objects.filter(
            Q(onboarding_completed=True) | Q(posts__status="published"),
        )
        .exclude(
            briefs__date=now_utc.date(),
        )
        .distinct()
    )

    # Filter to users whose preferred brief time has passed in their local tz
    users = []
    for user in candidates:
        try:
            user_tz = zoneinfo.ZoneInfo(user.timezone or "UTC")
        except (KeyError, Exception):
            user_tz = zoneinfo.ZoneInfo("UTC")
        user_local_now = now_utc.astimezone(user_tz)
        # Compare against the user's date (not UTC date) so day-boundary is correct
        if user_local_now.time() >= user.daily_brief_time:
            # Also check they don't already have a brief for THEIR local date
            if not user.briefs.filter(date=user_local_now.date()).exists():
                users.append(user)

    eligible_count = len(users)
    if not users:
        # Diagnostic: log why no users matched
        total_users = User.objects.count()
        onboarded = User.objects.filter(onboarding_completed=True).count()
        with_posts = User.objects.filter(posts__status="published").distinct().count()
        already_briefed = User.objects.filter(briefs__date=now_utc.date()).count()
        logger.debug(
            "Brief eligibility: %d total users, %d onboarded, %d with posts, "
            "%d candidates checked, %d already briefed today (UTC)",
            total_users, onboarded, with_posts, len(candidates), already_briefed,
        )

    generated = 0
    for user in users:
        try:
            brief = generate_daily_brief(user)
            if brief:
                generated += 1
        except Exception as e:
            logger.error("Failed to generate brief for %s: %s", user.email, e)

    if generated:
        logger.info("Daily brief run: generated %d briefs for %d eligible users", generated, eligible_count)
    return generated
