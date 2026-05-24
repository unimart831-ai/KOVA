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


# ─── Kova Score Calculation ──────────────────────────────────────────────────

def calculate_kova_score(user, brief_data, *, return_breakdown=False):
    """Calculate a 0-100 social media health score.

    Components (each weighted):
    - Pipeline health (30): Do you have content scheduled / are you publishing?
    - Engagement health (25): Are people interacting with your content?
    - Consistency (25): Have you posted regularly over the last 7 days?
    - Agent activity (20): Are your AI agents active and working?
    """
    breakdown = {
        "pipeline": {"points": 0, "max": 30, "label": "Pipeline health"},
        "engagement": {"points": 0, "max": 25, "label": "Engagement"},
        "consistency": {"points": 0, "max": 25, "label": "Consistency"},
        "agent_activity": {"points": 0, "max": 20, "label": "Agent activity"},
    }

    week = brief_data.get("week_stats", {})
    week_published = week.get("published", 0)
    scheduled = brief_data.get("scheduled_today", 0)
    pending = brief_data.get("pending_approval", 0)
    failed = brief_data.get("failed_posts", 0)

    pipeline_pts = 0
    if week_published >= 5:
        pipeline_pts = 30
    elif week_published >= 3:
        pipeline_pts = 22
    elif week_published >= 1:
        pipeline_pts = 14
    elif scheduled > 0 or pending > 0:
        pipeline_pts = 7
    if failed > 0:
        pipeline_pts -= min(10, failed * 4)
    breakdown["pipeline"]["points"] = max(0, pipeline_pts)

    engagement = brief_data.get("engagement", {})
    interactions = engagement.get("total_interactions", 0)
    engagement_pts = 0
    if interactions >= 20:
        engagement_pts = 25
    elif interactions >= 10:
        engagement_pts = 20
    elif interactions >= 5:
        engagement_pts = 14
    elif interactions >= 1:
        engagement_pts = 8
    breakdown["engagement"]["points"] = engagement_pts

    week_created = week.get("total_created", 0)
    consistency_pts = 0
    if week_created >= 7:
        consistency_pts = 25
    elif week_created >= 5:
        consistency_pts = 20
    elif week_created >= 3:
        consistency_pts = 13
    elif week_created >= 1:
        consistency_pts = 6
    breakdown["consistency"]["points"] = consistency_pts

    agent_actions = brief_data.get("agent_activity", [])
    active_agents = len({
        a.get("agent_type") or a.get("type", "")
        for a in agent_actions
        if (a.get("agent_type") or a.get("type", ""))
    })
    completed_actions = brief_data.get(
        "agent_completed_count",
        sum(1 for a in agent_actions if a.get("status") == "completed"),
    )
    agent_pts = 0
    if active_agents >= 4:
        agent_pts += 12
    elif active_agents >= 2:
        agent_pts += 8
    elif active_agents >= 1:
        agent_pts += 4
    if completed_actions >= 10:
        agent_pts += 8
    elif completed_actions >= 5:
        agent_pts += 5
    elif completed_actions >= 1:
        agent_pts += 2
    breakdown["agent_activity"]["points"] = agent_pts

    score = sum(c["points"] for c in breakdown.values())
    score = max(0, min(100, score))
    if return_breakdown:
        return score, breakdown
    return score


def _get_kova_score_delta(user, new_score):
    """Get the change from the previous brief's score."""
    from apps.briefs.models import DailyBrief
    prev_brief = (
        DailyBrief.objects.filter(user=user)
        .order_by("-date")
        .values_list("kova_score", flat=True)
        .first()
    )
    if prev_brief is not None and prev_brief > 0:
        return new_score - prev_brief
    return 0


# ─── While You Slept — overnight agent work ─────────────────────────────────

def _gather_overnight_work(user):
    """Summarize what agents did overnight (last 12 hours)."""
    from apps.agents.models import AgentAction
    from apps.briefs.operations_report import enrich_overnight_work
    from apps.content.models import Post, ContentSeed

    cutoff = timezone.now() - timedelta(hours=12)

    actions = AgentAction.objects.filter(
        user=user, created_at__gte=cutoff,
    )

    posts_created = ContentSeed.objects.filter(
        user=user, created_at__gte=cutoff,
    ).count()

    posts_drafted = Post.objects.filter(
        user=user, created_at__gte=cutoff,
        status__in=["draft", "pending_approval"],
    ).count()

    posts_published = Post.objects.filter(
        user=user, published_at__gte=cutoff,
        status="published",
    ).count()

    # Count by agent type
    agent_counts = dict(
        actions.values_list("agent_type")
        .annotate(cnt=Count("id"))
        .values_list("agent_type", "cnt")
    )

    # Trends discovered (research agent)
    trends_found = actions.filter(
        agent_type="research",
        action_type="discover_trends",
        status="completed",
    ).count()

    # Competitor analyses
    competitors_analyzed = actions.filter(
        agent_type__in=["research", "analyst"],
        action_type__icontains="competitor",
        status="completed",
    ).count()

    # Engagement handled
    engagements_handled = actions.filter(
        agent_type="engage",
        status="completed",
    ).count()

    total_actions = actions.filter(status="completed").count()

    return enrich_overnight_work(user, {
        "posts_created": posts_created,
        "posts_drafted": posts_drafted,
        "posts_published": posts_published,
        "trends_found": trends_found,
        "competitors_analyzed": competitors_analyzed,
        "engagements_handled": engagements_handled,
        "total_actions": total_actions,
        "active_agents": list(agent_counts.keys()),
    })


def _build_action_summary(user) -> dict:
    """Aggregate concrete agent actions over the last 24h.

    Powers the action-tense Daily Brief (Phase 3 W12). Where adapt_summary
    captures *learning*, this captures *doing* — the things the AI actually
    handled on the owner's behalf, plus what it couldn't and bumped up.

    Shape:
        {
            "engage": {
                "auto_sent": int,        # AI replies sent autonomously
                "escalated": int,        # comments routed to owner for review
                "drafts_pending": int,   # drafts awaiting owner approval
            },
            "reviews": {
                "scheduled": int,        # new ReviewRequests this window
                "sent": int,             # outreach fired
                "positive_seeds": int,   # content seeds auto-created from praise
                "negative_to_review": list[dict],  # escalations needing eyes
            },
            "walk_ins": int,             # WalkInEvents recorded
            "bookings_completed": int,   # Booking.status=completed transitions
        }
    """
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)

    summary = {
        "engage": {"auto_sent": 0, "escalated": 0, "drafts_pending": 0},
        "reviews": {
            "scheduled": 0, "sent": 0, "positive_seeds": 0,
            "negative_to_review": [],
        },
        "walk_ins": 0,
        "bookings_completed": 0,
    }

    try:
        from apps.engage.models import Interaction
        summary["engage"]["auto_sent"] = Interaction.objects.filter(
            user=user, status="auto_replied",
            updated_at__gte=cutoff,
        ).count()
        summary["engage"]["escalated"] = Interaction.objects.filter(
            user=user, status="flagged",
            updated_at__gte=cutoff,
        ).count()
        summary["engage"]["drafts_pending"] = Interaction.objects.filter(
            user=user, status="draft",
        ).count()
    except Exception:
        pass

    try:
        from apps.reviews.models import ReviewRequest
        rqs = ReviewRequest.objects.filter(user=user)
        summary["reviews"]["scheduled"] = rqs.filter(
            created_at__gte=cutoff,
        ).count()
        summary["reviews"]["sent"] = rqs.filter(
            sent_at__gte=cutoff,
        ).count()
        summary["reviews"]["positive_seeds"] = rqs.filter(
            content_seed__isnull=False,
            responded_at__gte=cutoff,
        ).count()
        neg = rqs.filter(
            escalated_in_brief=True,
            sentiment="negative",
            responded_at__gte=cutoff,
        )[:3]
        summary["reviews"]["negative_to_review"] = [
            {
                "customer": r.customer_name or "(anonymous)",
                "preview": (r.response_text or "")[:120],
            }
            for r in neg
        ]
    except Exception:
        pass

    try:
        from apps.qr_attribution.models import WalkInEvent
        summary["walk_ins"] = WalkInEvent.objects.filter(
            user=user, recorded_at__gte=cutoff,
        ).count()
    except Exception:
        pass

    try:
        from apps.bookings.models import Booking
        summary["bookings_completed"] = Booking.objects.filter(
            booking_link__user=user,
            status="completed",
            completed_at__gte=cutoff,
        ).count()
    except Exception:
        pass

    return summary


def _build_adapt_summary(user) -> dict:
    """Aggregate recent Adapt Agent v2 actions into a Daily-Brief-shaped summary.

    Reads AgentAction rows with agent_type="adapt" written in the last 24
    hours (or since the last brief, whichever is shorter) and produces:

        {
            "changes_count": int,
            "promotions": list[str],     # human-readable descriptors
            "retirements": list[str],
            "frequency_change": str,     # "+1 posts/week" or None
            "pillar_changes": list[str], # "+0.5 weight on Transformations"
        }

    The LLM uses these strings verbatim or paraphrases them — the
    prompt forbids generic "I'm learning your style" language.
    """
    from datetime import timedelta
    from apps.agents.models import AgentAction

    cutoff = timezone.now() - timedelta(hours=24)
    actions = list(
        AgentAction.objects
        .filter(user=user, agent_type="adapt", created_at__gte=cutoff)
        .order_by("-created_at")[:20]
    )
    summary = {
        "changes_count": 0,
        "promotions": [],
        "retirements": [],
        "frequency_change": None,
        "pillar_changes": [],
    }
    for a in actions:
        action_type = (a.action_type or "")
        input_data = a.input_data or {}
        output_data = a.output_data or {}
        if action_type == "promote_dna":
            combo = input_data.get("combo") or output_data.get("after_appends", {}).get("combo", {})
            descriptor = ", ".join(f"{k}={v}" for k, v in combo.items() if v)
            ratio = input_data.get("ratio")
            line = (
                f"{descriptor} ({ratio:.1f}× your average)"
                if isinstance(ratio, (int, float)) else descriptor
            )
            summary["promotions"].append(line)
        elif action_type == "retire_dna":
            combo = input_data.get("combo") or output_data.get("after_appends", {}).get("combo", {})
            descriptor = ", ".join(f"{k}={v}" for k, v in combo.items() if v)
            n = input_data.get("sample_size") or "?"
            rate = input_data.get("mean_engagement")
            tail = f" ({n} posts, {rate:.1%} avg)" if isinstance(rate, (int, float)) else ""
            summary["retirements"].append(f"{descriptor}{tail}")
        elif action_type == "reweight_pillar":
            pillar = input_data.get("pillar", "")
            before = output_data.get("before")
            after = output_data.get("after")
            if before is not None and after is not None:
                delta = round(float(after) - float(before), 2)
                sign = "+" if delta >= 0 else ""
                summary["pillar_changes"].append(f"{sign}{delta} weight on {pillar}")
        elif action_type == "adjust_frequency":
            before = output_data.get("before")
            after = output_data.get("after")
            if before is not None and after is not None:
                delta = int(after) - int(before)
                sign = "+" if delta > 0 else ""
                summary["frequency_change"] = f"{sign}{delta} posts/week (now {after})"

    summary["changes_count"] = (
        len(summary["promotions"]) + len(summary["retirements"])
        + len(summary["pillar_changes"]) + (1 if summary["frequency_change"] else 0)
    )
    return summary


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
    recent_actions_qs = AgentAction.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(hours=24),
    )
    recent_actions = recent_actions_qs.values("agent_type", "action_type", "status").order_by("-created_at")[:20]
    agent_completed_count = recent_actions_qs.filter(status="completed").count()

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
    research_updated_at = None
    try:
        from apps.agents.models import AgentAction as _AA
        latest_research_action = (
            _AA.objects.filter(
                user=user,
                agent_type="research",
                action_type="discover_trends",
                status=_AA.ActionStatus.COMPLETED,
            )
            .order_by("-created_at")
            .first()
        )
        if latest_research_action:
            trends = latest_research_action.output_data or {"trending_topics": [], "opportunity_briefs": []}
            research_updated_at = latest_research_action.created_at
        else:
            trends = {"trending_topics": [], "opportunity_briefs": []}
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

    # Product catalog intelligence
    try:
        from apps.products.utils import get_product_brief_data
        product_data = get_product_brief_data(user)
    except Exception as e:
        logger.warning("Product data for brief failed: %s", e)
        product_data = {}

    # Revenue attribution intelligence
    try:
        from apps.analytics.revenue import get_revenue_brief_data, get_revenue_headline_insight
        revenue_data = get_revenue_brief_data(user, days=7)
        # Headline insight is the single-sentence "what to tell the owner"
        # — same logic as the Revenue Dashboard top card. Used by the LLM
        # prompt so the brief surfaces "Post X drove KES Y" instead of a
        # generic "revenue is up" line.
        revenue_data["headline_insight"] = get_revenue_headline_insight(user, days=7)
    except Exception as e:
        logger.warning("Revenue data for brief failed: %s", e)
        revenue_data = {}

    # Adapt Agent v2 — what did the learning loop change since the last brief?
    # Reads recent AgentAction rows with agent_type="adapt" and bundles
    # them into a compact summary the LLM can paraphrase as a single
    # `adapt_update` line in the brief.
    try:
        adapt_summary = _build_adapt_summary(user)
    except Exception as e:
        logger.warning("Adapt summary for brief failed: %s", e)
        adapt_summary = {}

    try:
        action_summary = _build_action_summary(user)
    except Exception as e:
        logger.warning("Action summary for brief failed: %s", e)
        action_summary = {}

    try:
        from apps.briefs.operations_report import build_operations_report

        operations_report = build_operations_report(user, hours=24)
    except Exception as e:
        logger.warning("Operations report for brief failed: %s", e)
        operations_report = {"has_activity": False, "categories": [], "recent_tasks": []}

    # Posts created this week
    week_stats = Post.objects.filter(
        user=user,
        created_at__date__gte=week_ago,
    ).aggregate(
        total_created=Count("id"),
        published=Count("id", filter=Q(status=Post.Status.PUBLISHED)),
        failed=Count("id", filter=Q(status=Post.Status.FAILED)),
    )

    # ── Decisions needed: items requiring human judgment ──────────────
    # Unanswered interactions (new/flagged)
    try:
        from apps.engage.models import Interaction
        unanswered = Interaction.objects.filter(
            user=user,
            status__in=["new", "flagged"],
        ).order_by("-created_at")[:10]
        unanswered_data = [
            {
                "author": i.author_name,
                "content": i.content[:120],
                "platform": i.platform,
                "type": i.interaction_type,
                "status": i.status,
                "sentiment": i.sentiment,
            }
            for i in unanswered
        ]
        unanswered_count = Interaction.objects.filter(
            user=user, status__in=["new", "flagged"],
        ).count()
    except Exception as e:
        logger.warning("Unanswered interactions query failed: %s", e)
        unanswered_data = []
        unanswered_count = 0

    # New leads awaiting action
    try:
        from apps.leads.models import Lead
        new_leads = Lead.objects.filter(
            user=user, status="new",
        ).order_by("-created_at")[:5]
        new_leads_data = [
            {
                "name": l.name,
                "source": l.source,
                "created": l.created_at.strftime("%b %d"),
            }
            for l in new_leads
        ]
        new_leads_count = Lead.objects.filter(user=user, status="new").count()
        open_leads_count = Lead.objects.filter(
            user=user, status__in=["new", "contacted", "qualified"],
        ).count()
    except Exception as e:
        logger.warning("Leads query for brief failed: %s", e)
        new_leads_data = []
        new_leads_count = 0
        open_leads_count = 0

    decisions_needed = {
        "unanswered_interactions": unanswered_data,
        "unanswered_count": unanswered_count,
        "new_leads": new_leads_data,
        "new_leads_count": new_leads_count,
        "open_leads_count": open_leads_count,
        "posts_pending_approval": pending_posts,
        "failed_posts": failed_posts,
    }

    # Holiday awareness — upcoming moments + drafts already prepared
    holiday_context = {"upcoming": [], "drafts_ready": 0}
    try:
        from apps.calendar_intel.models import HolidayDraft
        from apps.calendar_intel.selectors import top_upcoming_for_brief
        upcoming = top_upcoming_for_brief(user, count=3)
        holiday_context["upcoming"] = [
            {
                "name": m.name,
                "date": m.date.isoformat(),
                "days_until": m.days_until,
                "score": m.score,
            }
            for m in upcoming
        ]
        holiday_context["drafts_ready"] = HolidayDraft.objects.filter(
            user=user,
            status=HolidayDraft.Status.DRAFTS_READY,
        ).count()
    except Exception as e:
        logger.warning("Holiday context for brief failed: %s", e)

    data = {
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
        "agent_completed_count": agent_completed_count,
        "performance": perf,
        "content_dna": dna_summary,
        "trends": trends,
        "research_updated_at": research_updated_at,
        "engagement": engagement,
        "competitor_intel": competitor_intel,
        "product_catalog": product_data,
        "revenue_attribution": revenue_data,
        "adapt_summary": adapt_summary,
        "action_summary": action_summary,
        "operations_report": operations_report,
        "decisions_needed": decisions_needed,
        "holiday_context": holiday_context,
    }

    # Flag whether this user has meaningful data for the strategist LLM.
    # New/inactive users with no posts or engagement produce hallucinated briefs.
    week = week_stats or {}
    has_meaningful_data = (
        week.get("published", 0) > 0
        or week.get("total_created", 0) > 0
        or engagement.get("total_interactions", 0) > 0
        or pending_posts > 0
        or operations_report.get("has_activity")
    )
    data["has_meaningful_data"] = has_meaningful_data

    return data


def _generate_brief_with_llm(user, brief_data):
    """Use LLM to compose a natural-language daily brief in agency-director tone.

    When the user has no meaningful data yet (new account, no posts, no engagement),
    switches to an onboarding-mode prompt that sets up next steps instead of
    generating analysis from empty data.
    """
    profile = getattr(user, "profile", None)
    company = getattr(profile, "company_name", "") if profile else ""
    # Use the centralized greeting helper — falls back to full_name's first
    # word, then company name, then email handle. Never returns "there".
    from apps.utils.greetings import greeting_name
    first_name = greeting_name(user)

    # ── Onboarding mode: no real data yet ──────────────────────────────────────
    if not brief_data.get("has_meaningful_data"):
        from apps.platforms.models import SocialAccount
        connected_platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
        )
        platform_list = ", ".join(connected_platforms) if connected_platforms else "none yet"

        onboarding_system = (
            "You are the Chief Strategist at Kova — an AI social media agency. "
            f"Your client is {first_name}, who runs '{company or 'their business'}'. "
            "They are brand new — no posts published, no engagement data yet. "
            "Your job is to be their first morning check-in: welcoming, encouraging, "
            "and giving them 2-3 concrete first steps to get momentum going. "
            "DO NOT invent performance metrics or fake engagement numbers. "
            "Respond in JSON with the same schema as always, but:\n"
            '- "summary": 3-4 sentences. Acknowledge they\'re just starting. Give 2 concrete first steps. Sound like an excited, expert partner.\n'
            '- "agent_plan": 2-3 things the agents will do today to set up for success (research, drafting first post ideas, etc)\n'
            '- "decisions_needed": 1-2 items to focus on this week (connect platforms, set brand voice, publish first post)\n'
            '- "trending_topics": [] (no trend data yet)\n'
            '- "suggested_posts": 2 post ideas to get started with, even without real data\n'
            '- "performance_highlight": "" (empty — no data yet)\n'
            '- All other fields: empty strings or empty lists\n'
            '- "mobile_digest": {headline: max 80 chars, whatsapp_body: max 200 chars, '
            'one-line morning ping for WhatsApp}\n'
        )
        onboarding_prompt = (
            f"Generate a welcoming first brief for {first_name}. "
            f"Connected platforms: {platform_list}. "
            "No posts published yet. No engagement data. Give them an energizing start."
        )
        return generate(
            prompt=onboarding_prompt,
            system=onboarding_system,
            model=get_model_for_task("strategist.brief", user=user),
            json_mode=True,
            temperature=0.6,
            max_tokens=1500,
        )

    # ── Standard mode — action-tense, AI-first-person (Phase 3 W12) ───────────
    system_prompt = (
        "You are Kova — the AI marketing operator running this account. "
        f"You are talking to {first_name}, who runs '{company}'.\n\n"
        "THIS IS NOT A REPORT FROM AN OUTSIDER. You ARE the system. "
        "You did the work last night. You learned the things. You handled the "
        "comments. Speak in the first person about your own actions. The owner "
        "wakes up to 'here's what I did' — not 'here's what was done'.\n\n"
        "Voice rules:\n"
        "- USE 'I' for your own actions ('I replied to 7 comments', 'I learned…', "
        "'I retired pattern X'). Never 'the agent' or 'we'.\n"
        "- USE 'you' for the owner — direct, no formal address.\n"
        "- Action-tense: past for what you did, present for what's blocked, "
        "future for the one move you're recommending.\n"
        "- Be specific: name posts, numbers, platforms, customer names.\n"
        "- SHORT SENTENCES. Punchy. No marketing-speak. No 'leverage', 'optimize', 'synergy'.\n"
        "- Honesty: if you couldn't handle something, say so plainly.\n\n"
        "Respond in JSON with these keys:\n"
        '- "summary": exactly 3 short paragraphs separated by \\n\\n. Structure:\n'
        f'  Paragraph 1 (I DID): Start with "{first_name}," — then a punchy recap '
        'of what you actually did in the last 24h. RULES: '
        '(1) SKIP any item with a count of 0 — never say "I auto-replied to 0 comments". '
        'If a whole category is empty, leave it out entirely. '
        '(2) If `action_summary` is all zeros, pivot to what agents DID do: '
        'trends discovered, posts drafted, research completed, content seeds created — '
        'draw from `agent_activity` and `overnight_work`. '
        '(3) Numbers only for things that actually happened. '
        'Example when active: "I auto-replied to 7 comments, recorded 2 walk-ins, '
        'and turned a 5-star testimonial into a content seed for you." '
        'Example when quiet: "I ran 5 background tasks — discovered 7 trends in your '
        'niche and drafted 3 post ideas while you were offline."\n'
        '  Paragraph 2 (I LEARNED / I COULDN\'T): The single most useful insight. '
        'Paraphrase `adapt_summary` if it has real changes. Then flag exactly ONE '
        'thing that needs the owner — a flagged comment, a negative review, an open lead. '
        'Use specific names or numbers. IMPORTANT: if performance data shows a metric '
        'that seems contradictory (e.g. comments exist but impressions show 0), flag it '
        'as a possible data sync issue, NOT as a platform crisis. Never use alarm words '
        'like "catastrophic", "critical failure", or "blocking" unless you have confirmed '
        'evidence. State the fact plainly: "7 Facebook posts show 0 impressions in the '
        'data — this may be a metrics sync delay or a real reach issue worth checking." '
        '2-3 short sentences.\n'
        '  Paragraph 3 (YOUR ONE MOVE): One concrete action the owner can take in '
        'under 5 minutes. Start with "Your move today:". Be hyper-specific: name the '
        'exact page, button, or setting — not "run a diagnostic". '
        'Bad: "Go to Facebook Business Suite and diagnose distribution." '
        'Good: "Open facebook.com/[page]/insights → Reach tab → check if the last 7 '
        'posts show Organic Reach = 0. If yes, check Page Quality at '
        'facebook.com/settings?tab=page_quality." '
        'If there is nothing urgent, give a growth move instead. 1-2 sentences.\n'
        '- "decisions_needed": list of 1-4 items needing human judgment, each with '
        '{item, context, recommended_action, urgency: "now"|"today"|"this_week"}. '
        'E.g. "3 flagged comments need your review", "A lead asked about pricing — reply recommended". '
        'Empty list if nothing needs attention.\n'
        '- "agent_plan": list of 2-4 things the agents will do today, each with '
        '{agent, action, why}. E.g. {agent: "Research", action: "Scanning competitor X\'s new campaign", '
        'why: "They posted 3x more than usual yesterday"}. Be specific, not generic.\n'
        '- "trending_topics": list of 3-5 relevant trending topics with '
        '{topic, relevance, urgency: "high"|"medium"|"low", suggested_angle, platforms: []}.\n'
        '- "suggested_posts": list of 2-3 content ideas with {idea, reasoning, platform} — '
        'grounded in what\'s working + what\'s trending. Not generic ideas.\n'
        '- "performance_highlight": 2-3 sentences — one standout insight from yesterday/this week. '
        'Connect it to strategy: not just "engagement up 20%" but "your behind-the-scenes posts '
        'are getting 3x more saves — we should do more of these."\n'
        '- "engagement_summary": 2-3 sentences — engagement health, response quality, '
        'superfans to acknowledge, sentiment shifts.\n'
        '- "pipeline_summary": 2-3 sentences about the sales/lead pipeline — '
        'new leads, open conversations, conversion opportunities. Empty string if no lead data.\n'
        '- "agent_summary": 1-2 sentences — what the AI agents accomplished in the last 24 hours. '
        'Specific actions, not "agents were active."\n'
        '- "competitor_update": 1-2 sentences if competitor data exists, empty string otherwise.\n'
        '- "product_update": 1-2 sentences if product catalog data exists, empty string otherwise.\n'
        '- "operations_update": 1-3 sentences summarizing automated tasks from '
        '`operations_report` — Snap to Sell, Batch Snap, carousels, motion reels, '
        'Receipt to Restock, voice briefs, content drafts, engagement replies. '
        'Name counts and specifics. Empty string if nothing ran.\n'
        '- "product_alerts": list of 0-3 product alerts needing attention, each with '
        '{item, severity: "critical"|"warning"|"info", action}. '
        'E.g. {item: "Scheduled posts promote an out-of-stock product", severity: "critical", '
        'action: "Pause or edit 2 posts mentioning Product X"}. '
        'Check product_catalog data for stock_content_mismatches, demand_signals, and never_promoted items.\n'
        '- "adapt_update": ONE concrete sentence in YOUR voice about what '
        'you (the AI) changed since the last brief. Use `adapt_summary` as '
        'truth. If `adapt_summary.changes_count == 0`, return empty string '
        '(do not fabricate learning). When there ARE changes, paraphrase '
        'the most impactful one. Format examples: '
        '"I\'ve started favouring [pattern X] — your last 3 posts using it '
        'got 2.4× your average."  OR  "I retired [pattern Y] — 5 posts '
        'averaged 0.2%."  Pick promotions over retirements over pillar '
        'reweights over frequency changes when multiple exist. NEVER say '
        'generic "I\'m learning your style" — name specifics or say nothing.\n'
        '- "actions_summary": ONE sentence in YOUR voice summarizing concrete '
        'things you handled in the last 24h. Use `action_summary` as truth. '
        'SKIP zero-count items entirely — only mention categories where N > 0. '
        'Format: "I auto-replied to N comments, recorded N walk-ins, and '
        'completed N bookings." Return empty string "" if everything is 0.\n'
        '- "escalations": list of 0-3 items you (the AI) could NOT handle '
        'and need the owner to look at. Each: {what, why_escalated, '
        'where_to_go}. E.g. {what: "Negative review from Mary", '
        'why_escalated: "sentiment dropped below threshold", '
        'where_to_go: "/reviews/<id>/"}. Pull from '
        '`action_summary.reviews.negative_to_review` and from `decisions_needed`.\n'
        '- "revenue_update": ONE concrete sentence about money. Use the '
        '`revenue_attribution.headline_insight` block as the source of truth. '
        'If `headline_insight.kind == "top_post"`, paraphrase its `headline` '
        'naturally — name the platform, the post topic (in quotes), and the '
        'KES amount. Add a second sentence ONLY if it gives the owner an '
        'action (e.g. "Consider 2 more like it this week."). '
        'If `kind == "no_revenue_in_window"`, say "No revenue attributed this '
        'window — open 90 days for the longer view." '
        'If `kind == "pipeline_warming"`, say "Pixel firing but no '
        'conversions yet — first attributed sale will land here." '
        'If `kind == "no_pixel"`, say "Install the Kova Pixel to start '
        'tracking which posts make money." '
        'If `kind == "no_pipeline"`, return an EMPTY string (do not mention '
        'revenue when there is literally no pipeline). '
        'NEVER use generic phrases like "revenue is up" or "great week" — '
        'always name specifics or say nothing.\n'
        '- "mobile_digest": {headline: max 80 chars punchy status line, '
        'whatsapp_body: max 200 chars, no newlines — morning ping with counts + '
        'one move; do NOT include URLs}\n'
    )

    holiday_hint = ""
    hctx = brief_data.get("holiday_context") or {}
    upcoming = hctx.get("upcoming") or []
    drafts_ready = hctx.get("drafts_ready") or 0
    close_moments = [m for m in upcoming if m.get("days_until", 999) <= 7]
    if drafts_ready > 0 or close_moments:
        bits = []
        if drafts_ready > 0:
            bits.append(f"{drafts_ready} holiday draft(s) are already prepared and waiting in Content Studio")
        if close_moments:
            top = close_moments[0]
            bits.append(
                f"{top['name']} is in {top['days_until']} day(s)"
            )
        holiday_hint = (
            "\n\nHOLIDAY CONTEXT (weave naturally into Paragraph 1 or 3 if relevant): "
            + "; ".join(bits) + ". "
            "If drafts are ready, the move today should reference reviewing them."
        )

    prompt = (
        f"Compile today's morning check-in based on this data:\n\n"
        f"{json.dumps(brief_data, indent=2, default=str)}\n\n"
        "Generate a strategic, personalized morning briefing. "
        "Be direct — tell the client what matters, what to do, and what we're handling. "
        "If something needs their decision, flag it clearly."
        f"{holiday_hint}"
    )

    response = generate(
        prompt=prompt,
        system=system_prompt,
        model=get_model_for_task("strategist.brief", user=user),
        json_mode=True,
        temperature=0.5,
        max_tokens=2500,
    )
    return response


def generate_daily_brief(user, *, user_date=None):
    """Generate a daily brief for a single user. Called by the periodic task.

    Args:
        user_date: The date in the user's local timezone. Falls back to UTC
                   date when not supplied (backward-compat).
    """
    today = user_date or timezone.now().date()

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

        # Calculate Kova Score and overnight work summary
        kova_score, score_breakdown = calculate_kova_score(
            user, brief_data, return_breakdown=True,
        )
        score_delta = _get_kova_score_delta(user, kova_score)
        overnight = _gather_overnight_work(user)

        mobile_digest = llm_result.get("mobile_digest") or {}
        if not isinstance(mobile_digest, dict):
            mobile_digest = {}

        brief = DailyBrief.objects.create(
            user=user,
            date=today,
            summary=llm_result.get("summary", "Your daily brief is ready."),
            trending_topics=trending_topics,
            suggested_posts=suggested_posts,
            performance_summary={
                "highlight": llm_result.get("performance_highlight", ""),
                "agent_summary": llm_result.get("agent_summary", ""),
                "engagement_summary": llm_result.get("engagement_summary", ""),
                "pipeline_summary": llm_result.get("pipeline_summary", ""),
                "competitor_update": llm_result.get("competitor_update", ""),
                "product_update": llm_result.get("product_update", ""),
                "operations_update": llm_result.get("operations_update", ""),
                "product_alerts": llm_result.get("product_alerts", []),
                "revenue_update": llm_result.get("revenue_update", ""),
                "adapt_update": llm_result.get("adapt_update", ""),
                "actions_summary": llm_result.get("actions_summary", ""),
                "escalations": llm_result.get("escalations", []),
                "decisions_needed": llm_result.get("decisions_needed", []),
                "dismissed_decisions": [],
                "agent_plan": llm_result.get("agent_plan", []),
                "score_breakdown": score_breakdown,
                "data": brief_data.get("performance", {}).get("performance_data", {}),
                "research_updated_at": brief_data.get("research_updated_at").isoformat() if brief_data.get("research_updated_at") else None,
                "is_onboarding_mode": not brief_data.get("has_meaningful_data", True),
                "operations_report": brief_data.get("operations_report", {}),
                "mobile_digest": mobile_digest,
            },
            agent_activity=[
                {"type": a["agent_type"], "action": a["action_type"], "status": a["status"]}
                for a in brief_data.get("agent_activity", [])
            ],
            posts_pending=brief_data["pending_approval"],
            kova_score=kova_score,
            kova_score_delta=score_delta,
            overnight_work=overnight,
        )

        # Create notification
        Notification.create_for_user(
            user=user,
            notification_type="system",
            message="Your daily brief is ready. Good morning!",
        )

        # Multi-channel delivery (email, WhatsApp, WebSocket)
        from apps.briefs.delivery import deliver_daily_brief
        deliver_daily_brief(user, brief)

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

    # Find users who MIGHT need a brief (active, onboarded or have published posts).
    # We intentionally do NOT pre-filter by date here — each user has their own
    # timezone, so UTC date is the wrong comparator. The per-user loop below
    # checks the user's LOCAL date and skips if a brief already exists for it.
    # This fixes a bug where users in UTC-N timezones could be incorrectly excluded
    # when their local date differs from the UTC date.
    candidates = list(
        User.objects.filter(
            Q(onboarding_completed=True) | Q(posts__status="published"),
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
            else:
                logger.info(
                    "Brief skip %s: already has brief for local date %s",
                    user.email, user_local_now.date(),
                )
        else:
            logger.info(
                "Brief skip %s: local time %s < brief time %s (tz=%s)",
                user.email, user_local_now.time().strftime("%H:%M"),
                user.daily_brief_time.strftime("%H:%M"), user.timezone or "UTC",
            )

    eligible_count = len(users)
    if not users:
        # Diagnostic: log why no users matched — INFO so it shows in production
        total_users = User.objects.count()
        onboarded = User.objects.filter(onboarding_completed=True).count()
        with_posts = User.objects.filter(posts__status="published").distinct().count()
        already_briefed = User.objects.filter(briefs__date=now_utc.date()).count()
        logger.info(
            "Brief eligibility: %d total users, %d onboarded, %d with published posts, "
            "%d candidates pre-time-filter, %d already briefed today (UTC). "
            "No eligible users found.",
            total_users, onboarded, with_posts, len(candidates), already_briefed,
        )

    generated = 0
    for user in users:
        try:
            # Pass the user's local date so inner function uses the same date
            import zoneinfo as _zi
            try:
                _utz = _zi.ZoneInfo(user.timezone or "UTC")
            except (KeyError, Exception):
                _utz = _zi.ZoneInfo("UTC")
            user_date = now_utc.astimezone(_utz).date()

            brief = generate_daily_brief(user, user_date=user_date)
            if brief:
                generated += 1
            else:
                logger.info("Brief generation returned None for %s (date=%s)", user.email, user_date)
        except Exception as e:
            logger.error("Failed to generate brief for %s: %s", user.email, e)

    if generated:
        logger.info("Daily brief run: generated %d briefs for %d eligible users", generated, eligible_count)
    return generated
