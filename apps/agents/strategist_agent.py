"""
Chief Strategist & Growth Advisor Agent — Orchestration & Autonomous Pipeline.

The brain of Kova. Coordinates all agents into a cohesive GROWTH strategy:
  1. Reviews Research Agent's latest trends → picks the best to act on
  2. Auto-creates ContentSeeds from trends → feeds to Create Agent
  3. Reviews Engage Agent data → identifies engagement patterns
  4. Tracks audience growth → correlates content types with follower growth
  5. Monitors revenue signals → click attribution and conversion tracking
  6. Compiles strategic recommendations → feeds into Daily Brief
  7. Adjusts content mix based on what GROWS the audience, not just engagement

Growth Intelligence:
  - Follower velocity per platform (accelerating/decelerating/steady)
  - Content-to-growth correlation (which content DNA drives follows)
  - Revenue signals (clicks, conversions, UTM attribution)
  - Growth assessment (AI diagnosis of what's working and what's not)

Autonomy Levels (driven by user's auto_approve_posts setting):
  - Manual: Strategist suggests seeds + schedule. User approves everything.
  - Autonomous: Strategist creates seeds, Create Agent generates, Adapt Agent schedules.
    User reviews in morning brief — can override.

Architecture:
  [Research Agent] ──→                                  ──→ [Create Agent]
  [Analyst Agent]  ──→  Chief Strategist (this file)   ──→ [Adapt Agent]
  [Engage Agent]   ──→                                  ──→ [Daily Brief]
  [Growth Data]    ──→                                  ──→ [Dashboard]
"""

import json
import logging
from datetime import timedelta

from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.agents.models import AgentAction, AgentConfig
from apps.analytics.competitor_intel import get_competitor_context_for_strategist
from apps.analytics.models import GrowthSnapshot, PostMetric
from apps.content.models import ContentSeed, Post
from apps.engage.models import Interaction
from apps.platforms.models import SocialAccount

logger = logging.getLogger(__name__)


# ─── Gather Intelligence ─────────────────────────────────────────────────────

def _gather_strategy_inputs(user):
    """
    Collect all intelligence from other agents that the Strategist needs
    to make decisions.
    """
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(hours=24)

    # 1. Latest Research Agent trends (last 24h)
    research_actions = (
        AgentAction.objects.filter(
            user=user,
            agent_type="research",
            action_type="discover_trends",
            status=AgentAction.ActionStatus.COMPLETED,
            created_at__gte=day_ago,
        )
        .order_by("-created_at")
        .first()
    )
    trends = research_actions.output_data if research_actions else {}

    # 2. Recent content performance (Analyst data)
    analyst_actions = (
        AgentAction.objects.filter(
            user=user,
            agent_type="analyst",
            status=AgentAction.ActionStatus.COMPLETED,
            created_at__gte=week_ago,
        )
        .order_by("-created_at")
        .first()
    )
    performance = analyst_actions.output_data if analyst_actions else {}

    # 3. Engagement patterns from Engage Agent
    engagement_stats = {
        "new_interactions_24h": Interaction.objects.filter(
            user=user, created_at__gte=day_ago,
        ).count(),
        "unanswered": Interaction.objects.filter(
            user=user, status=Interaction.Status.NEW, ai_suggested_reply="",
        ).count(),
        "flagged": Interaction.objects.filter(
            user=user, status=Interaction.Status.FLAGGED,
        ).count(),
        "sentiment_breakdown": _get_sentiment_breakdown(user, days=7),
        "top_engagers": _get_top_engagers(user, days=30),
    }

    # 4. Content pipeline state
    pipeline = {
        "pending_approval": Post.objects.filter(
            user=user, status=Post.Status.PENDING_APPROVAL,
        ).count(),
        "scheduled_upcoming": Post.objects.filter(
            user=user,
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
            scheduled_at__gte=now,
        ).count(),
        "published_this_week": Post.objects.filter(
            user=user, status=Post.Status.PUBLISHED,
            published_at__gte=week_ago,
        ).count(),
        "failed_recent": Post.objects.filter(
            user=user, status=Post.Status.FAILED,
            updated_at__gte=week_ago,
        ).count(),
        "seeds_today": ContentSeed.objects.filter(
            user=user, created_at__date=now.date(),
        ).count(),
    }

    # 5. Connected platforms
    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )

    # 6. User context
    profile = getattr(user, "profile", None)

    # 7. Competitor intelligence
    try:
        competitor_intel = get_competitor_context_for_strategist(user)
    except Exception as e:
        logger.warning("Competitor intel failed for strategist: %s", e)
        competitor_intel = {}

    # 8. Growth intelligence — follower velocity + content-to-growth correlation
    growth_summary = GrowthSnapshot.get_growth_summary(user, days=30)
    content_growth_correlation = _get_content_growth_correlation(user, days=30)
    revenue_signals = _get_revenue_signals(user, days=30)

    return {
        "trends": trends,
        "performance": performance,
        "engagement": engagement_stats,
        "pipeline": pipeline,
        "platforms": platforms,
        "competitor_intel": competitor_intel,
        "growth_intelligence": {
            "growth_summary": growth_summary,
            "content_growth_correlation": content_growth_correlation,
            "revenue_signals": revenue_signals,
        },
        "user_context": {
            "company": getattr(profile, "company_name", "") if profile else "",
            "industry": getattr(profile, "industry", "") if profile else "",
            "brand_voice": getattr(profile, "brand_voice", "") if profile else "",
            "goals": getattr(profile, "goals", []) if profile else [],
            "auto_approve": getattr(profile, "auto_approve_posts", False) if profile else False,
            "posting_frequency": getattr(profile, "posting_frequency", "daily") if profile else "daily",
        },
    }


def _get_sentiment_breakdown(user, days=7):
    """Get sentiment counts for recent interactions."""
    cutoff = timezone.now() - timedelta(days=days)
    interactions = Interaction.objects.filter(
        user=user, created_at__gte=cutoff,
    ).exclude(sentiment="")

    breakdown = {"positive": 0, "neutral": 0, "negative": 0}
    for sentiment in interactions.values_list("sentiment", flat=True):
        if sentiment in breakdown:
            breakdown[sentiment] += 1
    return breakdown


def _get_top_engagers(user, days=30):
    """Identify superfans — people who engage multiple times."""
    cutoff = timezone.now() - timedelta(days=days)
    engagers = {}

    interactions = Interaction.objects.filter(
        user=user,
        created_at__gte=cutoff,
    ).exclude(author_username="").values("author_username", "author_name")

    for item in interactions:
        username = item["author_username"]
        if username not in engagers:
            engagers[username] = {"name": item["author_name"], "count": 0}
        engagers[username]["count"] += 1

    # Return top 10 sorted by engagement count
    top = sorted(engagers.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    return [
        {"username": u, "name": data["name"], "interactions": data["count"]}
        for u, data in top
        if data["count"] >= 2  # at least 2 interactions = superfan candidate
    ]


def _get_content_growth_correlation(user, days=30):
    """
    Find which content DNA attributes correlate with follower growth.
    Compares content types published in a week vs. follower delta that week.
    Returns the top content attributes that drive audience growth.
    """
    from collections import defaultdict
    from datetime import date

    cutoff = timezone.now() - timedelta(days=days)

    # Get published posts with content_dna in the period
    posts = Post.objects.filter(
        user=user,
        status=Post.Status.PUBLISHED,
        published_at__gte=cutoff,
        content_dna__isnull=False,
    ).exclude(content_dna={}).select_related("social_account")

    if not posts.exists():
        return None

    # Get follower growth snapshots in the same period
    snapshots = GrowthSnapshot.objects.filter(
        user=user, snapshot_date__gte=cutoff.date(),
    ).order_by("snapshot_date")

    if snapshots.count() < 3:
        return None

    # Build a daily growth map: date → total follower delta across platforms
    daily_growth = {}
    for snap in snapshots:
        d = snap.snapshot_date
        daily_growth[d] = daily_growth.get(d, 0) + snap.followers_delta

    # For each content DNA attribute, calculate avg growth in the 3 days after publishing
    attribute_growth = defaultdict(lambda: {"total_growth": 0, "post_count": 0})

    for post in posts:
        if not post.published_at:
            continue
        pub_date = post.published_at.date()
        # Sum follower growth 1-3 days after this post
        growth_after = sum(
            daily_growth.get(pub_date + timedelta(days=d), 0)
            for d in range(1, 4)
        )

        dna = post.content_dna or {}
        for attr_key in ("format", "tone", "topic"):
            val = dna.get(attr_key)
            if val:
                key = f"{attr_key}:{val}"
                attribute_growth[key]["total_growth"] += growth_after
                attribute_growth[key]["post_count"] += 1

    if not attribute_growth:
        return None

    # Calculate avg growth per attribute and rank
    ranked = []
    for attr, data in attribute_growth.items():
        if data["post_count"] >= 2:  # need at least 2 posts for signal
            avg = round(data["total_growth"] / data["post_count"], 1)
            ranked.append({
                "attribute": attr,
                "avg_growth_after_post": avg,
                "post_count": data["post_count"],
            })

    ranked.sort(key=lambda x: x["avg_growth_after_post"], reverse=True)
    return {
        "growth_drivers": ranked[:5],
        "growth_killers": [r for r in ranked if r["avg_growth_after_post"] < 0][:3],
    }


def _get_revenue_signals(user, days=30):
    """
    Aggregate click/conversion attribution from posts.
    Uses PostMetric.clicks and Conversion model to show which platforms
    and content types drive the most traffic and revenue.
    """
    from collections import defaultdict
    from decimal import Decimal

    from apps.analytics.models import Conversion

    cutoff = timezone.now() - timedelta(days=days)

    # Click data from PostMetric
    posts_with_clicks = Post.objects.filter(
        user=user,
        status=Post.Status.PUBLISHED,
        published_at__gte=cutoff,
        metrics__clicks__gt=0,
    ).select_related("metrics", "social_account")

    platform_clicks = defaultdict(int)
    top_click_posts = []

    for post in posts_with_clicks[:50]:
        clicks = post.metrics.clicks
        platform = post.social_account.platform if post.social_account else "unknown"
        platform_clicks[platform] += clicks
        top_click_posts.append({
            "platform": platform,
            "clicks": clicks,
            "content_preview": post.content_text[:60],
            "published": str(post.published_at.date()) if post.published_at else "",
        })

    top_click_posts.sort(key=lambda x: x["clicks"], reverse=True)

    # Revenue from Conversion model
    conversions = Conversion.objects.filter(
        user=user, created_at__gte=cutoff,
    )
    total_revenue = sum(c.revenue for c in conversions) if conversions.exists() else Decimal("0")
    conversion_count = conversions.count()

    if not platform_clicks and not conversion_count:
        return None

    return {
        "total_clicks": sum(platform_clicks.values()),
        "clicks_by_platform": dict(platform_clicks),
        "top_click_posts": top_click_posts[:5],
        "total_revenue": float(total_revenue),
        "conversions": conversion_count,
    }


# ─── Strategic Decision Making ───────────────────────────────────────────────

def run_strategy_cycle(user):
    """
    Main orchestration cycle. Called daily (before Daily Brief generation).

    Steps:
      1. Gather intelligence from all agents
      2. Ask LLM to make strategic decisions
      3. Execute decisions: create seeds, adjust schedule, flag issues
      4. Return strategy report for Daily Brief

    Returns dict with strategy outputs.
    """
    config = AgentConfig.objects.filter(user=user, agent_type="strategist").first()
    if config and not config.is_active:
        logger.info("Strategist disabled for %s, skipping", user.email)
        return {"status": "disabled", "seeds_created": 0, "recommendations": []}

    action = AgentAction.objects.create(
        user=user,
        agent_type="strategist",
        action_type="strategy_cycle",
        description="Running daily strategy cycle — coordinating all agents",
    )

    try:
        # Step 1: Gather all intelligence
        inputs = _gather_strategy_inputs(user)

        # Step 2: Ask LLM for strategic decisions
        decisions = _make_strategic_decisions(user, inputs)

        # Step 3: Execute decisions
        seeds_created = _execute_proactive_seeds(user, decisions, inputs)

        # Step 4: Build strategy report
        report = {
            "status": "completed",
            "seeds_created": seeds_created,
            "recommendations": decisions.get("recommendations", []),
            "content_plan": decisions.get("content_plan", []),
            "engagement_insights": decisions.get("engagement_insights", ""),
            "growth_assessment": decisions.get("growth_assessment", {}),
            "alerts": decisions.get("alerts", []),
            "superfans": inputs["engagement"].get("top_engagers", []),
            "growth_summary": inputs.get("growth_intelligence", {}).get("growth_summary"),
        }

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = report
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "completed_at"])

        logger.info(
            "Strategy cycle complete for %s: %d seeds created, %d recommendations",
            user.email, seeds_created, len(report["recommendations"]),
        )
        return report

    except Exception as e:
        logger.exception("Strategy cycle failed for %s: %s", user.email, e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return {"status": "failed", "seeds_created": 0, "recommendations": [], "error": str(e)}


def _make_strategic_decisions(user, inputs):
    """
    Feed all intelligence to LLM and get back strategic decisions:
    - Which trends to act on (create proactive content)
    - Content mix recommendations
    - Engagement strategy adjustments
    - Alerts/warnings
    """
    profile = getattr(user, "profile", None)
    company = getattr(profile, "company_name", "") if profile else ""

    # Determine how many seeds to create based on posting frequency
    # posting_frequency is an int (posts per week), convert to daily target
    freq = inputs["user_context"].get("posting_frequency", 5)
    if isinstance(freq, int):
        target_posts = max(1, round(freq / 7 * 2))  # ~2 days' worth of seeds
    else:
        freq_map = {"few_weekly": 2, "daily": 3, "multiple_daily": 5}
        target_posts = freq_map.get(freq, 3)

    # Account for what's already queued
    already_queued = inputs["pipeline"]["pending_approval"] + inputs["pipeline"]["scheduled_upcoming"]
    seeds_needed = max(0, target_posts - already_queued)

    system_prompt = (
        "You are the Chief Strategist & Growth Advisor for Kova, an AI social media platform.\n"
        f"Brand: {company}\n\n"
        "You coordinate all other agents. Your job is to make GROWTH-DRIVEN strategic decisions based on:\n"
        "- Research Agent's trend data (what's happening in the market)\n"
        "- Analyst Agent's performance data (what content is working)\n"
        "- Engage Agent's interaction data (what the audience is saying)\n"
        "- Content pipeline state (what's queued, pending, published)\n"
        "- Growth Intelligence (follower velocity, content-to-growth correlation, revenue signals)\n\n"
        "THINK STRATEGICALLY — GROWTH FIRST:\n"
        "- Prioritize content that GROWS THE AUDIENCE, not just engages existing followers.\n"
        "- Study the content-to-growth correlation: double down on content DNA that drives follows.\n"
        "- Track growth velocity per platform — shift energy toward platforms gaining momentum.\n"
        "- If a platform's growth is decelerating, diagnose why and recommend corrections.\n"
        "- Don't just pick the hottest trend — pick trends that ALIGN with the brand AND drive growth.\n"
        "- If certain content types drive clicks/revenue, call that out explicitly.\n"
        "- Consider content mix: don't suggest 3 promotional posts in a row.\n"
        "- If engagement sentiment is negative, address it in the strategy.\n"
        "- Use competitor intelligence to find content gaps they're missing.\n"
        "- Flag any risks or issues that need human attention.\n\n"
        f"The user needs approximately {seeds_needed} new content ideas "
        f"(they have {already_queued} already queued, target is ~{target_posts}/day).\n"
        f"If {seeds_needed} is 0, focus on recommendations and insights instead.\n\n"
        "Respond in JSON with these keys:\n"
        '"content_plan": list of content seed objects to create, each with:\n'
        '  - "idea": the content seed idea (2-3 sentences, specific and actionable)\n'
        '  - "reasoning": why this idea right now (1 sentence)\n'
        '  - "source": "trend" | "performance" | "engagement" | "gap" | "seasonal" | "growth"\n'
        '  - "priority": "high" | "medium"\n'
        '  - "platforms": list of target platforms\n\n'
        '"recommendations": list of 2-4 strategic recommendations, each with:\n'
        '  - "action": what to do (1 sentence)\n'
        '  - "reasoning": why (1 sentence)\n'
        '  - "urgency": "now" | "this_week" | "ongoing"\n\n'
        '"engagement_insights": 1-2 sentences about engagement patterns and what they mean\n\n'
        '"growth_assessment": your assessment of audience growth health. Include:\n'
        '  - "status": "growing" | "stagnant" | "declining"\n'
        '  - "velocity": brief description of growth speed\n'
        '  - "best_platform": which platform is growing fastest and why\n'
        '  - "action_items": 1-3 specific actions to accelerate growth\n\n'
        '"alerts": list of any warnings or issues (e.g., "Negative sentiment trending up — '
        'consider addressing customer complaints publicly"). Empty list if none.\n'
    )

    # Build a concise input summary (avoid sending raw massive JSON)
    trending = inputs["trends"].get("trending_topics", [])[:5]
    opportunities = inputs["trends"].get("opportunity_briefs", [])[:3]

    prompt = (
        f"Today: {timezone.now().strftime('%A, %B %d, %Y')}\n\n"
        f"=== TRENDS (from Research Agent) ===\n"
        f"{json.dumps(trending, indent=2, default=str)}\n\n"
        f"=== OPPORTUNITIES ===\n"
        f"{json.dumps(opportunities, indent=2, default=str)}\n\n"
        f"=== PERFORMANCE (from Analyst Agent) ===\n"
        f"{json.dumps(inputs['performance'], indent=2, default=str)[:1500]}\n\n"
        f"=== ENGAGEMENT (from Engage Agent) ===\n"
        f"New interactions (24h): {inputs['engagement']['new_interactions_24h']}\n"
        f"Unanswered: {inputs['engagement']['unanswered']}\n"
        f"Flagged: {inputs['engagement']['flagged']}\n"
        f"Sentiment (7d): {json.dumps(inputs['engagement']['sentiment_breakdown'])}\n"
        f"Top engagers: {json.dumps(inputs['engagement']['top_engagers'][:5], default=str)}\n\n"
        f"=== PIPELINE STATE ===\n"
        f"Pending approval: {inputs['pipeline']['pending_approval']}\n"
        f"Scheduled upcoming: {inputs['pipeline']['scheduled_upcoming']}\n"
        f"Published this week: {inputs['pipeline']['published_this_week']}\n"
        f"Failed recent: {inputs['pipeline']['failed_recent']}\n\n"
        f"=== PLATFORMS ===\n"
        f"Connected: {', '.join(inputs['platforms'])}\n\n"
        f"=== COMPETITOR INTELLIGENCE ===\n"
        f"{json.dumps(inputs.get('competitor_intel', {}), indent=2, default=str)[:1500]}\n\n"
    )

    # Growth intelligence section
    gi = inputs.get("growth_intelligence", {})
    growth_summary = gi.get("growth_summary")
    content_growth = gi.get("content_growth_correlation")
    revenue = gi.get("revenue_signals")

    if growth_summary:
        prompt += (
            f"=== GROWTH INTELLIGENCE (Follower Velocity) ===\n"
            f"{json.dumps(growth_summary, indent=2, default=str)}\n\n"
        )

    if content_growth:
        prompt += (
            f"=== CONTENT-TO-GROWTH CORRELATION ===\n"
            f"Growth drivers (content types that grow followers):\n"
            f"{json.dumps(content_growth.get('growth_drivers', []), indent=2, default=str)}\n"
        )
        killers = content_growth.get("growth_killers", [])
        if killers:
            prompt += f"Growth killers (content types that lose followers):\n{json.dumps(killers, indent=2, default=str)}\n"
        prompt += "\n"

    if revenue:
        prompt += (
            f"=== REVENUE SIGNALS ===\n"
            f"Total clicks (30d): {revenue.get('total_clicks', 0)}\n"
            f"Clicks by platform: {json.dumps(revenue.get('clicks_by_platform', {}))}\n"
            f"Total revenue: ${revenue.get('total_revenue', 0):.2f}\n"
            f"Conversions: {revenue.get('conversions', 0)}\n"
            f"Top click posts: {json.dumps(revenue.get('top_click_posts', [])[:3], indent=2, default=str)}\n\n"
        )

    prompt += (
        f"=== USER GOALS ===\n"
        f"{json.dumps(inputs['user_context'].get('goals', []))}\n\n"
    )

    # Intelligence: inject past strategy outcomes so Strategist learns from itself
    from apps.agents.memory import get_strategy_history, get_prediction_accuracy
    strategy_history = get_strategy_history(user)
    if strategy_history:
        prompt += f"\n{strategy_history}\n"

    accuracy = get_prediction_accuracy(user, days=14)
    if accuracy.get("validated_count", 0) > 0:
        prompt += (
            f"=== CONTENT PREDICTION ACCURACY (last 14 days) ===\n"
            f"Accurate within ±10: {accuracy['accuracy_rate']}%\n"
            f"Avg predicted: {accuracy['avg_predicted']}, Avg actual: {accuracy['avg_actual']}\n"
            f"Use this to calibrate expectations for new content.\n\n"
        )

    prompt += (
        f"Make strategic decisions. Create up to {seeds_needed} content ideas "
        f"(0 if queue is full). Always provide recommendations and insights."
    )

    response = generate(
        prompt=prompt,
        system=system_prompt,
        model=get_model_for_task("strategist.decide", user=user),
        json_mode=True,
        temperature=0.5,
        max_tokens=3500,
    )

    try:
        result = parse_llm_json(response.content)
    except (json.JSONDecodeError, ValueError):
        # Retry once with a stricter JSON instruction
        logger.warning("Strategist: first attempt returned non-JSON, retrying")
        retry_response = generate(
            prompt=prompt + "\n\nCRITICAL: You MUST respond with a valid JSON object only. No prose, no markdown. Just the JSON.",
            system=system_prompt,
            model=get_model_for_task("strategist.decide", user=user),
            json_mode=True,
            temperature=0.3,
            max_tokens=3500,
        )
        try:
            result = parse_llm_json(retry_response.content)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Strategist: retry also returned non-JSON, using fallback")
            result = {
                "content_plan": [],
                "recommendations": [],
                "engagement_insights": "",
                "alerts": [],
            }

    return result


# ─── Execute Proactive Seeds ─────────────────────────────────────────────────

def _execute_proactive_seeds(user, decisions, inputs):
    """
    Create ContentSeeds from the Strategist's content plan.
    These go through the normal pipeline: seed → Create Agent → posts.

    Seeds are marked with source="strategist" so we can track autonomous
    vs. human-initiated content.
    """
    content_plan = decisions.get("content_plan", [])
    if not content_plan:
        return 0

    created = 0
    for item in content_plan:
        idea = item.get("idea", "").strip()
        if not idea:
            continue

        # Check for duplicates — don't create seeds too similar to recent ones
        recent_seeds = ContentSeed.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(hours=48),
        ).values_list("idea", flat=True)

        # Simple duplicate check — if any recent seed starts with the same 50 chars
        idea_prefix = idea[:50].lower()
        if any(s.lower().startswith(idea_prefix) for s in recent_seeds):
            logger.info("Skipping duplicate seed: %s...", idea[:60])
            continue

        # Determine target platforms
        platforms = item.get("platforms", [])
        valid_platforms = [
            p for p in platforms if p in inputs["platforms"]
        ]

        # Create the seed
        seed = ContentSeed.objects.create(
            user=user,
            idea=idea,
            notes=f"[Strategist Agent] {item.get('reasoning', '')}\nSource: {item.get('source', 'trend')}",
            target_platforms=valid_platforms if valid_platforms else [],
        )

        # Trigger Create Agent via Celery task
        from apps.content.tasks import generate_from_seed
        generate_from_seed.delay(str(seed.id))

        created += 1
        logger.info("Strategist created proactive seed: %s", idea[:80])

    return created


# ─── Engagement Report (for Daily Brief) ─────────────────────────────────────

def get_engagement_report(user, days=7):
    """
    Generate an engagement summary for the Daily Brief.
    Called by briefs/tasks.py when compiling the brief.
    """
    cutoff = timezone.now() - timedelta(days=days)

    interactions = Interaction.objects.filter(
        user=user, created_at__gte=cutoff,
    )

    total = interactions.count()
    if total == 0:
        return {
            "total_interactions": 0,
            "summary": "No interactions in the last week.",
            "top_interactions": [],
            "response_rate": 0,
            "superfans": [],
        }

    responded = interactions.filter(
        status__in=[Interaction.Status.AI_REPLIED, Interaction.Status.USER_REPLIED]
    ).count()

    response_rate = round((responded / total) * 100) if total > 0 else 0

    # Top interactions (flagged + negative first)
    top_interactions = list(
        interactions.filter(
            status__in=[Interaction.Status.FLAGGED, Interaction.Status.NEW],
        )
        .exclude(sentiment="positive")
        .order_by("-created_at")
        .values("author_name", "content", "sentiment", "interaction_type", "status")[:5]
    )

    # Platform breakdown
    platform_counts = {}
    for item in interactions.values("social_account__platform"):
        p = item["social_account__platform"]
        platform_counts[p] = platform_counts.get(p, 0) + 1

    return {
        "total_interactions": total,
        "responded": responded,
        "response_rate": response_rate,
        "sentiment": _get_sentiment_breakdown(user, days),
        "by_platform": platform_counts,
        "top_interactions": top_interactions,
        "superfans": _get_top_engagers(user, days),
        "growth_summary": GrowthSnapshot.get_growth_summary(user, days=7),
    }
