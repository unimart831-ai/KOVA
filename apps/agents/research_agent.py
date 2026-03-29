"""
Research Agent — Trend Discovery & Opportunity Intelligence.

Responsibilities:
  1. Detect trending topics relevant to the user's industry/niche
  2. Generate content opportunity briefs (ideas backed by trending data)
  3. Monitor competitor-adjacent themes
  4. Feed trending data into the Daily Brief
"""

import json
import logging
from datetime import timedelta

from django.utils import timezone

from apps.agents.llm import generate
from apps.agents.models import AgentAction, AgentConfig
from apps.content.models import Post

logger = logging.getLogger(__name__)


def _get_user_context(user):
    """Build context about the user's brand, audience, and recent content."""
    profile = getattr(user, "profile", None)
    recent_posts = (
        Post.objects.filter(user=user, status=Post.Status.PUBLISHED)
        .order_by("-published_at")
        .values_list("content_text", flat=True)[:10]
    )

    return {
        "company": getattr(profile, "company_name", "") if profile else "",
        "industry": getattr(profile, "industry", "") if profile else "",
        "brand_voice": getattr(profile, "brand_voice", "") if profile else "",
        "target_audience": getattr(profile, "target_audience", "") if profile else "",
        "content_pillars": getattr(profile, "content_pillars", []) if profile else [],
        "goals": getattr(profile, "goals", []) if profile else [],
        "recent_topics": [text[:100] for text in recent_posts],
    }


def discover_trends(user):
    """
    Research Agent: Discover trending topics and content opportunities
    relevant to the user's niche/industry.

    Uses LLM to synthesize trend signals based on:
    - User's industry and content pillars
    - Current date context (seasonality, events)
    - Recent content history (avoid repetition)

    Returns dict with trending_topics and opportunity_briefs.
    """
    # Check if research agent is active
    config = AgentConfig.objects.filter(
        user=user, agent_type="research"
    ).first()
    if config and not config.is_active:
        logger.info("Research agent disabled for %s, skipping", user.email)
        return {"trending_topics": [], "opportunity_briefs": []}

    action = AgentAction.objects.create(
        user=user,
        agent_type="research",
        action_type="discover_trends",
        description="Scanning for trending topics and content opportunities",
    )

    try:
        ctx = _get_user_context(user)
        today = timezone.now().date()

        # Custom instructions from agent config
        custom_instructions = ""
        if config and config.custom_instructions:
            custom_instructions = f"\nUser's custom research instructions: {config.custom_instructions}\n"

        system_prompt = (
            "You are the Research Agent for a social media intelligence platform. "
            "Your job is to discover trending topics, emerging conversations, and content "
            "opportunities that are specifically relevant to this user's brand and audience.\n\n"
            "Think like a trend analyst + content strategist. Focus on:\n"
            "- What's happening RIGHT NOW in their industry\n"
            "- Emerging conversations their audience cares about\n"
            "- Seasonal/timely hooks for the current date\n"
            "- Gaps in their recent content that represent opportunities\n"
            "- Cross-industry trends they could ride\n\n"
            "Be SPECIFIC — not generic. 'AI in marketing' is too broad. "
            "'Brands using AI-generated customer testimonials in Instagram Reels' is specific.\n\n"
            f"{custom_instructions}"
            "Respond in JSON with these keys:\n"
            '"trending_topics": list of 5-8 trending topic objects, each with:\n'
            '  - "topic": specific topic/theme (not just a hashtag)\n'
            '  - "relevance": why this matters to the user\'s brand (1 sentence)\n'
            '  - "urgency": "high" | "medium" | "low" — how time-sensitive is this\n'
            '  - "suggested_angle": a specific content angle they could take\n'
            '  - "platforms": list of best platforms for this topic\n\n'
            '"opportunity_briefs": list of 3-4 content opportunity objects, each with:\n'
            '  - "title": catchy brief title\n'
            '  - "description": 2-3 sentences explaining the opportunity\n'
            '  - "content_type": "post" | "thread" | "story" | "reel" | "carousel"\n'
            '  - "platform": best platform for this\n'
            '  - "timing": "today" | "this_week" | "upcoming"\n'
            '  - "why_now": why this opportunity exists right now\n'
        )

        prompt = (
            f"Date: {today.strftime('%A, %B %d, %Y')}\n\n"
            f"Brand: {ctx['company'] or 'Not specified'}\n"
            f"Industry: {ctx['industry'] or 'General'}\n"
            f"Target audience: {ctx['target_audience'] or 'Not specified'}\n"
            f"Content pillars: {json.dumps(ctx['content_pillars']) if ctx['content_pillars'] else 'Not specified'}\n"
            f"Goals: {json.dumps(ctx['goals']) if ctx['goals'] else 'Not specified'}\n"
            f"Brand voice: {ctx['brand_voice'] or 'Not specified'}\n\n"
            f"Recent content topics (to avoid repetition):\n"
            f"{json.dumps(ctx['recent_topics'], indent=2)}\n\n"
            "Discover trending topics and content opportunities for this brand. "
            "Be specific and actionable."
        )

        response = generate(
            prompt=prompt,
            system=system_prompt,
            json_mode=True,
            temperature=0.6,
            max_tokens=2000,
        )

        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning("Research Agent LLM returned non-JSON, wrapping")
            result = {
                "trending_topics": [],
                "opportunity_briefs": [],
                "raw_analysis": response.content,
            }

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = result
        action.tokens_used = response.total_tokens
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "completed_at"])

        logger.info(
            "Research Agent found %d trends and %d opportunities for %s",
            len(result.get("trending_topics", [])),
            len(result.get("opportunity_briefs", [])),
            user.email,
        )
        return result

    except Exception as e:
        logger.exception("Research Agent failed for %s: %s", user.email, e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return {"trending_topics": [], "opportunity_briefs": []}


def generate_content_angles(user, topic):
    """
    Given a specific trending topic, generate multiple content angles
    the user could pursue across different platforms.

    This is called when a user clicks "Explore" on a trending topic
    from their Daily Brief.
    """
    ctx = _get_user_context(user)

    action = AgentAction.objects.create(
        user=user,
        agent_type="research",
        action_type="generate_content_angles",
        description=f"Generating content angles for: {topic[:80]}",
        input_data={"topic": topic},
    )

    try:
        system_prompt = (
            "You are a content strategist. Given a trending topic and user brand context, "
            "generate 4-6 unique content angles — each tailored for a different platform or format.\n\n"
            "Respond in JSON with key 'angles', a list of objects:\n"
            '  - "angle": the specific angle/hook (1 sentence)\n'
            '  - "platform": best platform for this angle\n'
            '  - "format": post type (tweet, carousel, reel, story, article, thread)\n'
            '  - "opening_line": a draft opening line/hook\n'
            '  - "why_it_works": brief explanation of why this angle works\n'
        )

        prompt = (
            f"Trending topic: {topic}\n\n"
            f"Brand: {ctx['company']}\n"
            f"Industry: {ctx['industry']}\n"
            f"Brand voice: {ctx['brand_voice']}\n"
            f"Target audience: {ctx['target_audience']}\n\n"
            "Generate platform-specific content angles for this topic."
        )

        response = generate(
            prompt=prompt,
            system=system_prompt,
            json_mode=True,
            temperature=0.7,
            max_tokens=1500,
        )

        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"angles": [], "raw": response.content}

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = result
        action.tokens_used = response.total_tokens
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "completed_at"])

        return result

    except Exception as e:
        logger.exception("Content angle generation failed: %s", e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return {"angles": []}
