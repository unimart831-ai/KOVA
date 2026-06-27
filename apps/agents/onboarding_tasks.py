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


def _enrich_research_with_competitor_hints(user, research: dict) -> dict:
    """Add competitor landscape hints for welcome brief."""
    from apps.analytics.models import Competitor

    profile = getattr(user, "profile", None)
    company = (getattr(profile, "company_name", "") or "your space").strip()
    industry = getattr(profile, "industry", "") or ""
    space_label = industry.replace("_", " ") if industry else company
    tracked = list(
        Competitor.objects.filter(user=user, is_active=True).values_list("name", flat=True)[:5]
    )
    research = dict(research or {})
    if tracked:
        research["competitor_hints"] = tracked
        research["competitor_landscape"] = f"Tracking {len(tracked)} competitor(s): {', '.join(tracked)}."
    else:
        research["competitor_landscape"] = (
            f"For {space_label}, watch local leaders on Instagram and TikTok — "
            "add competitors in Analytics to unlock gap analysis."
        )
    return research


# If the intelligence task hasn't finished within this window, assume Celery
# dropped the job or it wedged. Surface a stuck state so the user can retry
# instead of polling forever.
STUCK_AFTER_SECONDS = 90


def get_onboarding_progress(user):
    """Check which onboarding intelligence steps are complete.

    Returns a dict with:
      steps     — list of {key, status} for each step
      all_done  — True when every step is completed or failed
      stuck     — True when STUCK_AFTER_SECONDS has elapsed since dispatch
                  and the chain is still not all_done
    """
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

    stuck = False
    started_at = getattr(getattr(user, "profile", None), "onboarding_intelligence_started_at", None)
    if not all_done and started_at:
        elapsed = (timezone.now() - started_at).total_seconds()
        if elapsed > STUCK_AFTER_SECONDS:
            stuck = True

    return {"steps": steps, "all_done": all_done, "stuck": stuck}


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

    progress = get_onboarding_progress(user)
    if progress["all_done"]:
        logger.info("Onboarding intelligence already complete for %s — skipping Celery run", user.email)
        return {"skipped": True, "reason": "already_complete"}

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
        research = _enrich_research_with_competitor_hints(user, research)
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
        description="Planning onboarding campaign proposals from research",
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
        description="Building draft posts for your first campaign",
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
                    posts = run_create_agent(seed, force_pending=True)
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

    try:
        user.profile.record_onboarding_step("intelligence_completed")
    except Exception:
        logger.exception("record_onboarding_step failed for %s", user.email)

    # Fire-and-forget completion ping (WhatsApp template). Soft-fails — never
    # blocks the chain on a messaging error.
    try:
        _send_completion_whatsapp_ping(user)
    except Exception:
        logger.exception("WhatsApp completion ping failed for %s", user.email)

    logger.info("Onboarding intelligence complete for %s: %s", user.email, result)
    return result


def _send_completion_whatsapp_ping(user) -> bool:
    """Send a 'your AI agency is ready' WhatsApp template to the user's phone.

    All three of these must be true or we no-op silently:
      * `settings.KOVA_ONBOARDING_TEMPLATE_NAME` is set
      * `settings.WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN` are set
      * the user has a phone_number we can route to E.164

    Returns True if a message was actually dispatched, False otherwise.
    """
    from django.conf import settings

    template_name = getattr(settings, "KOVA_ONBOARDING_TEMPLATE_NAME", "") or ""
    if not template_name:
        logger.debug("Onboarding ping: KOVA_ONBOARDING_TEMPLATE_NAME not set — skipping")
        return False

    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    if not (phone_id and token):
        logger.debug("Onboarding ping: master WhatsApp creds missing — skipping")
        return False

    from apps.accounts.phone_utils import phone_to_whatsapp_digits

    raw_phone = (getattr(user, "phone_number", "") or "").strip()
    to_number = phone_to_whatsapp_digits(raw_phone)
    if not to_number:
        logger.debug("Onboarding ping: user %s has no valid phone — skipping", user.email)
        return False

    first_name = (user.full_name or user.email or "there").split(" ")[0]
    from apps.accounts.onboarding_redirects import post_onboarding_site_path

    next_step_url = post_onboarding_site_path(user)
    components = [{
        "type": "body",
        "parameters": [
            {"type": "text", "text": first_name},
            {"type": "text", "text": next_step_url},
        ],
    }]

    from apps.platforms.providers.whatsapp import WhatsAppProvider
    provider = WhatsAppProvider()
    result = provider.send_template_message(
        access_token=token,
        to=to_number,
        template_name=template_name,
        language_code=getattr(settings, "KOVA_ONBOARDING_TEMPLATE_LANG", "en"),
        components=components,
        phone_number_id=phone_id,
    )
    if result.get("success"):
        logger.info("Onboarding ping sent to %s (%s)", user.email, to_number)
        return True
    logger.warning("Onboarding ping send failed for %s: %s", user.email, result.get("error"))
    return False


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
        "3. Explains the first campaign drafts you've prepared and the strategic thinking behind them\n"
        "4. Gives a clear 7-day roadmap for building their presence\n"
        "5. Makes them feel like they've hired a smart agency, not installed a tool\n\n"
        "Write in a confident, warm, strategic tone. Be specific — reference actual "
        "trends and opportunities. Make the user feel like their AI team is already ahead.\n\n"
        "Respond in JSON with these keys:\n"
        '"summary": 4-6 sentences — the main welcome message + what you found + what\'s ready\n'
        '"trending_topics": top 5 trending topics from research (list of {topic, relevance, urgency, suggested_angle, platforms})\n'
        '"suggested_posts": 3-5 campaign opportunities with {idea, reasoning, platform} — grounded in the research\n'
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
        f"We've prepared {seeds_created} campaign proposals and generated {posts_created} draft posts.\n\n"
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
        posts_pending=posts_created,
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
