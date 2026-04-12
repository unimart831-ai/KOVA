"""
Post-Onboarding Intelligence — "Agency First Meeting" Experience.

When a user finishes onboarding (Step 4), this task chain fires:
  1. Research Agent → discover trends in user's industry
  2. Create starter seeds from research opportunity briefs
  3. Generate posts for each seed via Create Agent
  4. Generate a Welcome Brief — a special first-time strategic briefing

The user is redirected to a completion page that polls for progress
and lights up each step as it finishes.
"""

import json
import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


# ─── Progress tracking via AgentAction ───────────────────────────────────────
# Each step creates an AgentAction with a specific action_type so the
# polling endpoint can check which steps are complete.

ONBOARDING_STEPS = {
    "research": "onboarding_research",
    "seeds": "onboarding_seeds",
    "content": "onboarding_content",
    "brief": "onboarding_brief",
}


def get_onboarding_progress(user):
    """Check which onboarding intelligence steps are complete."""
    from apps.agents.models import AgentAction

    actions = AgentAction.objects.filter(
        user=user,
        action_type__startswith="onboarding_",
    ).values_list("action_type", "status")

    completed = set()
    running = set()
    failed = set()
    for action_type, status in actions:
        if status == "completed":
            completed.add(action_type)
        elif status == "failed":
            failed.add(action_type)
        else:
            running.add(action_type)

    steps = []
    for key, action_type in ONBOARDING_STEPS.items():
        if action_type in completed:
            status = "completed"
        elif action_type in failed:
            status = "failed"
        elif action_type in running:
            status = "running"
        else:
            status = "pending"
        steps.append({"key": key, "status": status})

    all_done = all(s["status"] in ("completed", "failed") for s in steps)
    return {"steps": steps, "all_done": all_done}


@shared_task(name="agents.run_onboarding_intelligence", soft_time_limit=300, time_limit=360)
def run_onboarding_intelligence(user_id):
    """
    Post-onboarding task chain: Research → Seeds → Content → Welcome Brief.
    Creates the "agency first meeting" experience where the user sees
    their AI team already working on their brand.
    """
    from apps.agents.models import AgentAction

    try:
        user = User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        logger.error("Onboarding intelligence: user %s not found", user_id)
        return {"error": "User not found"}

    profile = user.profile
    result = {}

    # ── Step 1: Research Agent — discover industry trends ────────────
    research_action = AgentAction.objects.create(
        user=user,
        agent_type="research",
        action_type=ONBOARDING_STEPS["research"],
        description="Analyzing your industry and discovering trends",
    )
    try:
        from apps.agents.research_agent import discover_trends
        research = discover_trends(user)
        research_action.status = AgentAction.ActionStatus.COMPLETED
        research_action.output_data = research
        research_action.save(update_fields=["status", "output_data", "updated_at"])
        result["research"] = research
        logger.info("Onboarding research complete for %s: %d topics",
                     user.email, len(research.get("trending_topics", [])))
    except Exception as e:
        research_action.status = AgentAction.ActionStatus.FAILED
        research_action.error_message = str(e)
        research_action.save(update_fields=["status", "error_message", "updated_at"])
        logger.error("Onboarding research failed for %s: %s", user.email, e)
        research = {"trending_topics": [], "opportunity_briefs": []}
        result["research"] = research

    # ── Step 2: Create starter seeds from opportunity briefs ─────────
    seeds_action = AgentAction.objects.create(
        user=user,
        agent_type="strategist",
        action_type=ONBOARDING_STEPS["seeds"],
        description="Creating starter content ideas from research",
    )
    try:
        seeds = _create_starter_seeds(user, research)
        seeds_action.status = AgentAction.ActionStatus.COMPLETED
        seeds_action.output_data = {"seed_count": len(seeds), "seed_ids": [str(s.id) for s in seeds]}
        seeds_action.save(update_fields=["status", "output_data", "updated_at"])
        result["seeds"] = len(seeds)
    except Exception as e:
        seeds_action.status = AgentAction.ActionStatus.FAILED
        seeds_action.error_message = str(e)
        seeds_action.save(update_fields=["status", "error_message", "updated_at"])
        logger.error("Onboarding seed creation failed for %s: %s", user.email, e)
        seeds = []
        result["seeds"] = 0

    # ── Step 3: Generate posts from seeds via Create Agent ───────────
    content_action = AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type=ONBOARDING_STEPS["content"],
        description="Generating platform-optimized posts from your ideas",
    )
    try:
        from apps.platforms.models import SocialAccount
        has_platforms = SocialAccount.objects.filter(user=user, is_active=True).exists()

        if has_platforms:
            # Normal path: Create Agent generates per-platform posts
            total_posts = 0
            from apps.agents.create_agent import run_create_agent
            for seed in seeds:
                try:
                    posts = run_create_agent(seed)
                    total_posts += len(posts)
                except Exception as e:
                    logger.warning("Onboarding content gen failed for seed %s: %s", seed.id, e)
                    seed.status = "failed"
                    seed.error_message = str(e)
                    seed.save(update_fields=["status", "error_message", "updated_at"])
        else:
            # No platforms connected yet: generate platform-agnostic drafts
            # User can assign to platforms later when they connect
            total_posts = _generate_draft_posts_without_platforms(user, seeds)

        content_action.status = AgentAction.ActionStatus.COMPLETED
        content_action.output_data = {"posts_created": total_posts, "has_platforms": has_platforms}
        content_action.save(update_fields=["status", "output_data", "updated_at"])
        result["posts"] = total_posts
        logger.info("Onboarding content complete for %s: %d posts (platforms=%s)",
                     user.email, total_posts, has_platforms)
    except Exception as e:
        content_action.status = AgentAction.ActionStatus.FAILED
        content_action.error_message = str(e)
        content_action.save(update_fields=["status", "error_message", "updated_at"])
        logger.error("Onboarding content generation failed for %s: %s", user.email, e)
        result["posts"] = 0

    # ── Step 4: Generate Welcome Brief ───────────────────────────────
    brief_action = AgentAction.objects.create(
        user=user,
        agent_type="strategist",
        action_type=ONBOARDING_STEPS["brief"],
        description="Preparing your personalized welcome brief",
    )
    try:
        brief = _generate_welcome_brief(user, research, result)
        brief_action.status = AgentAction.ActionStatus.COMPLETED
        brief_action.output_data = {"brief_id": str(brief.id)}
        brief_action.save(update_fields=["status", "output_data", "updated_at"])
        result["brief_id"] = str(brief.id)
    except Exception as e:
        brief_action.status = AgentAction.ActionStatus.FAILED
        brief_action.error_message = str(e)
        brief_action.save(update_fields=["status", "error_message", "updated_at"])
        logger.error("Onboarding welcome brief failed for %s: %s", user.email, e)

    logger.info("Onboarding intelligence complete for %s: %s", user.email, result)
    return result


def _create_starter_seeds(user, research):
    """
    Create 3-5 ContentSeeds from Research Agent's opportunity briefs.
    These become the user's first batch of AI-generated content.
    """
    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount

    opportunity_briefs = research.get("opportunity_briefs", [])
    trending = research.get("trending_topics", [])

    # Get user's connected platforms
    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )

    seeds = []

    # Create seeds from opportunity briefs (prefer these — they're richer)
    for brief in opportunity_briefs[:3]:
        idea = brief.get("title", "")
        description = brief.get("description", "")
        if not idea:
            continue

        seed = ContentSeed.objects.create(
            user=user,
            idea=f"{idea}: {description}" if description else idea,
            notes=f"Auto-generated from research. Why now: {brief.get('why_now', '')}",
            target_platforms=platforms or [],
        )
        seeds.append(seed)

    # If we don't have enough from briefs, use trending topics
    if len(seeds) < 3:
        for topic in trending[:5]:
            if len(seeds) >= 5:
                break
            topic_text = topic.get("topic", "") if isinstance(topic, dict) else str(topic)
            angle = topic.get("suggested_angle", "") if isinstance(topic, dict) else ""
            if not topic_text:
                continue

            idea = f"{topic_text}: {angle}" if angle else topic_text
            seed = ContentSeed.objects.create(
                user=user,
                idea=idea,
                notes="Auto-generated from trending research. Review and customize these posts in the Studio.",
                target_platforms=platforms or [],
            )
            seeds.append(seed)

    # Fallback: if research returned nothing, create generic industry seeds
    if not seeds:
        profile = user.profile
        industry = getattr(profile, "industry", "") or "business"
        offerings = getattr(profile, "key_offerings", []) or []
        company = getattr(profile, "company_name", "") or "your brand"

        fallback_ideas = [
            f"Introduce {company} — who we are, what we do, and why we're different",
            f"Share a behind-the-scenes look at how {company} operates",
            f"Common misconceptions about {industry} that our audience should know",
        ]
        if offerings:
            fallback_ideas.append(f"Spotlight on our top offering: {offerings[0]}")

        for idea in fallback_ideas[:3]:
            seed = ContentSeed.objects.create(
                user=user,
                idea=idea,
                notes="Starter content to get your feed going. Edit freely!",
                target_platforms=platforms or [],
            )
            seeds.append(seed)

    logger.info("Created %d starter seeds for %s", len(seeds), user.email)
    return seeds


def _generate_draft_posts_without_platforms(user, seeds):
    """
    Generate platform-agnostic draft posts when user hasn't connected any platforms.
    Uses the Create Agent's LLM to write content, but stores as drafts
    without a social_account. User assigns to platforms later.
    """
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json
    from apps.content.models import ContentSeed, Post

    profile = user.profile
    company = getattr(profile, "company_name", "") or "your brand"
    industry = getattr(profile, "industry", "") or "business"
    voice = getattr(profile, "brand_voice", "") or ""
    tone = getattr(profile, "tone", "") or "professional"
    language = getattr(profile, "content_language", "en") or "en"

    total = 0
    for seed in seeds:
        seed.status = ContentSeed.SeedStatus.PROCESSING
        seed.save(update_fields=["status", "updated_at"])

        system_prompt = (
            "You are a social media content strategist. "
            f"Create 3 different social media posts for '{company}' ({industry}). "
            f"Brand voice: {voice or tone}. Content language: {language}.\n\n"
            "Each post should take a DIFFERENT angle on the topic. "
            "Make posts ready for social media — concise, engaging, with hooks. "
            "Include relevant emojis and hashtags where appropriate.\n\n"
            "Respond in JSON: {\"posts\": [{\"content\": \"...\", \"angle\": \"...\", "
            "\"best_platform\": \"twitter|linkedin|instagram|facebook|tiktok\"}]}"
        )

        prompt = (
            f"Topic/idea: {seed.idea}\n"
            f"Additional context: {seed.notes}\n\n"
            "Write 3 distinct social media posts, each with a different angle."
        )

        try:
            response = generate(
                prompt=prompt,
                system=system_prompt,
                model=get_model_for_task("create.content", user=user),
                json_mode=True,
                temperature=0.7,
                max_tokens=1500,
            )
            result = parse_llm_json(response.content)
            posts_data = result.get("posts", [])

            for p in posts_data[:3]:
                content = p.get("content", "").strip()
                if not content:
                    continue

                Post.objects.create(
                    user=user,
                    seed=seed,
                    social_account=None,
                    platform=p.get("best_platform", ""),
                    content_text=content,
                    ai_original_text=content,
                    ai_angle=p.get("angle", ""),
                    status=Post.Status.DRAFT,
                    generated_by_agent="create",
                    ai_reasoning="Generated during onboarding (no platform connected). Assign to a platform to schedule.",
                )
                total += 1

            seed.status = ContentSeed.SeedStatus.COMPLETED
            seed.save(update_fields=["status", "updated_at"])

        except Exception as e:
            logger.warning("Draft post generation failed for seed %s: %s", seed.id, e)
            seed.status = ContentSeed.SeedStatus.FAILED
            seed.error_message = str(e)
            seed.save(update_fields=["status", "error_message", "updated_at"])

    logger.info("Generated %d draft posts (no platforms) for %s", total, user.email)
    return total


def _generate_welcome_brief(user, research, onboarding_result):
    """
    Generate a special welcome brief — the user's first "agency meeting."
    Different from the daily brief: more strategic, more introductory,
    connects the dots between research findings and the content plan.
    """
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json
    from apps.briefs.models import DailyBrief

    profile = user.profile
    company = getattr(profile, "company_name", "") or "your brand"
    industry = getattr(profile, "industry", "") or "your industry"
    today = timezone.now().date()

    # Don't overwrite if a brief already exists for today
    existing = DailyBrief.objects.filter(user=user, date=today).first()
    if existing:
        return existing

    topics_count = len(research.get("trending_topics", []))
    posts_created = onboarding_result.get("posts", 0)
    seeds_created = onboarding_result.get("seeds", 0)

    system_prompt = (
        "You are the Chief Strategist Agent for Kova, an AI business intelligence platform. "
        "You're writing the user's FIRST welcome briefing — their first 'agency meeting.' "
        f"The user's brand is '{company}' in the '{industry}' space.\n\n"
        "This is NOT a daily update. This is a strategic welcome that:\n"
        "1. Shows you've already done research on their industry\n"
        "2. Summarizes what you discovered and why it matters\n"
        "3. Explains the starter content you've prepared and the strategic thinking behind it\n"
        "4. Gives a clear 7-day roadmap for building their presence\n"
        "5. Makes them feel like they've hired a smart agency, not installed a tool\n\n"
        "Write in a confident, warm, strategic tone. Be specific — reference actual "
        "trends and opportunities. Make the user feel like their AI team is already ahead.\n\n"
        "Respond in JSON with these keys:\n"
        '"summary": 4-6 sentences — the main welcome message + what you found + what\'s ready\n'
        '"trending_topics": top 5 trending topics from research (list of {topic, relevance, urgency, suggested_angle, platforms})\n'
        '"suggested_posts": 3-5 content ideas with {idea, reasoning, platform} — grounded in the research\n'
        '"performance_highlight": a strategic observation about their industry or niche opportunity\n'
        '"engagement_summary": advice on engaging with their audience in the first week\n'
        '"agent_summary": what each of the 6 agents will do for them this week\n'
        '"competitor_update": initial competitor landscape observation (even without specific competitors)\n'
        '"revenue_update": ""\n'
        '"product_update": ""\n'
    )

    prompt = (
        f"Welcome briefing for {company} ({industry}).\n\n"
        f"Research findings: {json.dumps(research, default=str)[:3000]}\n\n"
        f"We've created {seeds_created} content ideas and generated {posts_created} platform posts.\n\n"
        "Compose a welcome brief that shows the user their AI agency is already working. "
        "Reference specific trends and opportunities from the research. Make it feel personal and strategic."
    )

    response = generate(
        prompt=prompt,
        system=system_prompt,
        model=get_model_for_task("strategist.brief", user=user),
        json_mode=True,
        temperature=0.5,
        max_tokens=2000,
    )

    try:
        llm_result = parse_llm_json(response.content)
    except (json.JSONDecodeError, ValueError):
        llm_result = {
            "summary": (
                f"Welcome to Kova! Your AI agency is already at work. "
                f"We've analyzed {industry} trends and found {topics_count} relevant topics. "
                f"{posts_created} posts are ready for your review in the Studio. "
                f"Let's build your social presence together."
            ),
            "trending_topics": research.get("trending_topics", [])[:5],
            "suggested_posts": [],
            "performance_highlight": f"Your {industry} industry is active right now — great timing to start.",
            "engagement_summary": "",
            "agent_summary": "All 6 agents are active and learning your brand.",
        }

    brief = DailyBrief.objects.create(
        user=user,
        date=today,
        summary=llm_result.get("summary", "Welcome to Kova! Your AI agency is ready."),
        trending_topics=llm_result.get("trending_topics", []),
        suggested_posts=llm_result.get("suggested_posts", []),
        performance_summary={
            "highlight": llm_result.get("performance_highlight", ""),
            "agent_summary": llm_result.get("agent_summary", ""),
            "engagement_summary": llm_result.get("engagement_summary", ""),
            "competitor_update": llm_result.get("competitor_update", ""),
        },
        agent_activity=[],
        posts_pending=0,
    )

    # Create notification
    from apps.notifications.models import Notification
    Notification.create_for_user(
        user=user,
        notification_type="system",
        message="Your welcome brief is ready — your AI agency has already started working!",
    )

    logger.info("Welcome brief created for %s", user.email)
    return brief
