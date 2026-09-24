"""Shared onboarding completion and URL-inference helpers."""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

SETUP_TOTAL_STEPS = 1


def setup_step_for_wizard(step: int) -> int:
    """Single onboarding screen — always step 1."""
    return 1


def has_brand_voice_captured(profile) -> bool:
    """True when the user supplied voice guidance or at least one example post."""
    if (profile.brand_voice or "").strip():
        return True
    examples = profile.brand_voice_examples or []
    return any((e or "").strip() for e in examples)


def parse_brand_voice_examples(example_1: str, example_2: str = "", example_3: str = "") -> list[str]:
    """Normalize up to three sample posts from the voice step form."""
    out = []
    for raw in (example_1, example_2, example_3):
        text = (raw or "").strip()
        if text:
            out.append(text[:2200])
    return out[:3]


def apply_url_inference_to_profile(profile, data: dict) -> list[str]:
    """
    Persist URL inference JSON onto UserProfile without overwriting user edits.
    Returns list of field names that were updated.
    """
    updated = []

    def _set_if_empty(field, value):
        if value is None or value == "" or value == []:
            return
        current = getattr(profile, field, None)
        if current not in (None, "", []):
            return
        setattr(profile, field, value)
        updated.append(field)

    _set_if_empty("company_name", data.get("company_name"))
    _set_if_empty("website_url", data.get("website_url"))
    if data.get("industry"):
        valid = {v for v, _ in profile.Industry.choices}
        if data["industry"] in valid:
            _set_if_empty("industry", data["industry"])
    _set_if_empty("target_audience", data.get("target_audience"))
    if data.get("content_pillars"):
        _set_if_empty("content_pillars", data["content_pillars"])
    if data.get("key_offerings"):
        _set_if_empty("key_offerings", data["key_offerings"])

    if updated:
        profile.save()
    return updated


def _looks_like_post_caption(text: str) -> bool:
    """Heuristic: real sample posts vs a business-description blurb."""
    t = (text or "").strip()
    if not t or len(t) < 24:
        return False
    lower = t.lower()
    blurb_markers = (
        "we run",
        "we are",
        "we're a",
        "i run",
        "my business",
        "our business",
        "we help",
        "we sell",
        "ecommerce business",
        "e-commerce business",
    )
    if any(lower.startswith(m) or f" {m} " in f" {lower} " for m in blurb_markers):
        # Still allow if it clearly looks like a caption (hook + emoji/hashtag/line breaks)
        if "\n" in t or "#" in t or any(ch in t for ch in "🔥✨💪🙌"):
            return True
        return False
    return True


def _template_starter_captions(profile) -> list[dict]:
    """Deterministic, publishable captions from brand context (no LLM)."""
    company = (profile.company_name or "our brand").strip()
    what = (profile.brand_voice or "").strip()
    audience = (profile.target_audience or "").strip()
    industry = (getattr(profile, "industry", "") or "").replace("_", " ").strip()

    who = audience or "the people we serve"
    hook_what = what[:140].rstrip(".") if what else f"what makes {company} different"
    reason = what[:120].rstrip(".") if what else "the usual options were not built for you"
    proof = what[:160] if what else "Real people. Real results. Local first."
    industry_bit = f" in {industry}" if industry else ""

    return [
        {
            "content": (
                f"Meet {company}.\n\n"
                f"{hook_what}.\n\n"
                f"Built for {who}{industry_bit}.\n\n"
                "Follow along — we're just getting started."
            ),
            "angle": "Brand intro",
            "platform": "instagram",
            "cta_type": "none",
        },
        {
            "content": (
                f"If you're {who}, this is for you.\n\n"
                f"{company} exists because {reason}.\n\n"
                "Tell us what you need most — reply or DM."
            ),
            "angle": "Audience hook",
            "platform": "facebook",
            "cta_type": "whatsapp",
        },
        {
            "content": (
                f"A quick look at how {company} helps {who}.\n\n"
                f"{proof}\n\n"
                "Save this for later — and share it with someone who needs it."
            ),
            "angle": "Value proof",
            "platform": "instagram",
            "cta_type": "none",
        },
    ]


def _llm_starter_captions(user, profile) -> list[dict]:
    """Ask the LLM for 3 ready-to-post captions. Returns [] on any failure."""
    try:
        from apps.create.agents.llm import generate, get_model_for_task, parse_llm_json
    except Exception:
        return []

    company = (profile.company_name or "the business").strip()
    what = (profile.brand_voice or "").strip()
    examples = [e.strip() for e in (profile.brand_voice_examples or []) if e and str(e).strip()]
    audience = (profile.target_audience or "").strip()
    industry = (getattr(profile, "industry", "") or "").replace("_", " ")

    system = (
        "You are a social media copywriter for African SMEs. "
        "Write short, publish-ready posts — never paste a business description as a caption. "
        "Fix grammar. Use a warm, clear voice. "
        "Respond ONLY with JSON: "
        '{"posts":[{"content":"...","angle":"...","platform":"instagram|facebook|whatsapp","cta_hint":"..."}]}'
    )
    prompt = (
        f"Company: {company}\n"
        f"Industry: {industry or 'general'}\n"
        f"Audience: {audience or 'local customers'}\n"
        f"What they do (CONTEXT ONLY — do not paste as the post): {what or 'n/a'}\n"
        f"Sample posts (style reference): {examples[:2] or 'none'}\n\n"
        "Write exactly 3 different posts:\n"
        "1) Brand intro (Instagram)\n"
        "2) Audience problem → how you help (Facebook)\n"
        "3) Soft CTA / engagement ask (Instagram)\n"
        "Each 400–900 characters. Include light emoji where natural. No hashtag spam."
    )

    try:
        response = generate(
            prompt=prompt,
            system=system,
            model=get_model_for_task("create.content", user=user),
            json_mode=True,
            temperature=0.7,
            max_tokens=1200,
        )
        data = parse_llm_json(response.content)
        posts = data.get("posts") or []
        out = []
        for p in posts[:3]:
            content = (p.get("content") or "").strip()
            if len(content) < 40:
                continue
            # Guard: if model still pasted the blurb, skip that item
            if what and content.lower().startswith(what.lower()[:40]):
                continue
            out.append(
                {
                    "content": content[:2200],
                    "angle": (p.get("angle") or "Starter")[:120],
                    "platform": (p.get("platform") or "instagram").lower()[:20],
                    "cta_type": (p.get("cta_hint") or "none")[:20],
                }
            )
        return out
    except Exception:
        logger.exception("LLM starter captions failed for %s", getattr(user, "email", user))
        return []


def _attach_starter_graphic(post, profile) -> None:
    """Attach a simple branded graphic so Instagram drafts aren't blocked on media."""
    try:
        from apps.create.agents.graphics import GraphicType, generate_branded_graphic

        company = (profile.company_name or "Your brand").strip()
        generate_branded_graphic(
            post,
            GraphicType.CTA_BANNER,
            headline=company[:48],
            subtext=((profile.brand_voice or "")[:80] or "Built for your customers"),
            cta_text="Follow for more",
        )
    except Exception:
        logger.exception("Starter graphic failed for post %s", getattr(post, "pk", None))


def seed_onboarding_preview_posts(user) -> int:
    """
    Create instant, publishable draft posts for the WOW screen.

    Never dumps the raw "What do you do?" blurb into content_text.
    Prefers LLM captions; falls back to strong templates. Attaches a graphic
    to the first Instagram-bound draft so approve isn't blocked on media.
    """
    from apps.create.content.models import Post

    profile = user.profile
    if Post.objects.filter(user=user, generated_by_agent="onboarding_seed").exists():
        return 0

    captions: list[dict] = []

    # Real sample posts the user typed can be used as-is (polished lightly later by Celery).
    for raw in (profile.brand_voice_examples or [])[:2]:
        text = (raw or "").strip()
        if _looks_like_post_caption(text):
            captions.append(
                {
                    "content": text[:2200],
                    "angle": "Your sample",
                    "platform": "instagram",
                    "cta_type": "",
                }
            )

    if len(captions) < 3:
        llm_posts = _llm_starter_captions(user, profile)
        for p in llm_posts:
            if len(captions) >= 3:
                break
            captions.append(p)

    if len(captions) < 3:
        for p in _template_starter_captions(profile):
            if len(captions) >= 3:
                break
            captions.append(p)

    if not captions:
        return 0

    created = 0
    for i, item in enumerate(captions[:3]):
        platform = item.get("platform") or "instagram"
        if platform not in ("instagram", "facebook", "whatsapp", "twitter", "linkedin"):
            platform = "instagram"
        post = Post.objects.create(
            user=user,
            content_text=item["content"][:2200],
            ai_original_text=item["content"][:2200],
            ai_angle=item.get("angle") or "Onboarding starter",
            ai_reasoning=(
                "Drafted from your brand during onboarding. "
                "Review, add a photo if you want, then approve."
            ),
            status=Post.Status.PENDING_APPROVAL,
            generated_by_agent="onboarding_seed",
            platform=platform,
            cta_type=(item.get("cta_type") or "none")[:20],
        )
        if i == 0 and platform in ("instagram", "facebook"):
            _attach_starter_graphic(post, profile)
        created += 1
    return created


def ensure_instant_onboarding_wow(user) -> bool:
    """
    Sync bootstrap so the WOW screen shows real drafts + brief immediately.

    Marks research / campaign plan / welcome brief as instant-complete so the
    checklist can light up — but leaves **content** incomplete so Celery
    `run_onboarding_intelligence` still enriches (LLM research + better posts).
    """
    from apps.create.agents.models import AgentAction
    from apps.create.agents.onboarding_tasks import ONBOARDING_STEPS
    from apps.create.briefs.models import DailyBrief
    from apps.create.content.models import Post

    profile = user.profile
    company = (profile.company_name or "your business").strip()
    brand_snippet = (profile.brand_voice or "").strip()
    brand_preview = brand_snippet[:160] + ("…" if len(brand_snippet) > 160 else "")

    seed_onboarding_preview_posts(user)

    post_count = Post.objects.filter(
        user=user,
        status__in=[Post.Status.PENDING_APPROVAL, Post.Status.DRAFT],
    ).count()

    audience = (profile.target_audience or "").strip() or "customers"
    opportunity_briefs = [
        {
            "title": f"Introduce {company}",
            "description": brand_preview or f"Who {company} is and what you offer",
            "why_now": "First impression on social",
        },
        {
            "title": f"Prove why {audience} choose you",
            "description": "Show the problem you solve in plain language",
            "why_now": "Build trust early",
        },
        {
            "title": f"Invite a conversation with {company}",
            "description": "Soft CTA — DM, reply, or WhatsApp",
            "why_now": "Turn followers into leads",
        },
    ]

    stub_research = {
        "trending_topics": [
            {
                "topic": f"Content angles for {company}",
                "suggested_angle": "Lead with customer pain, then your proof — not a company bio",
            }
        ],
        "opportunity_briefs": opportunity_briefs[:3],
        "source": "brand_description",
        "instant": True,
    }

    completed = AgentAction.ActionStatus.COMPLETED

    def _mark_complete(step_key: str, agent_type: str, description: str, output_data: dict) -> None:
        action_type = ONBOARDING_STEPS[step_key]
        existing = AgentAction.objects.filter(user=user, action_type=action_type).first()
        if existing:
            if existing.status == completed:
                return
            if existing.status == AgentAction.ActionStatus.STARTED:
                return
        AgentAction.objects.update_or_create(
            user=user,
            action_type=action_type,
            defaults={
                "agent_type": agent_type,
                "description": description,
                "status": completed,
                "output_data": output_data,
                "error_message": "",
            },
        )

    def _mark_pending(step_key: str, agent_type: str, description: str) -> None:
        """Ensure content shows as Working until Celery finishes enrichment."""
        action_type = ONBOARDING_STEPS[step_key]
        existing = AgentAction.objects.filter(user=user, action_type=action_type).first()
        if existing and existing.status == completed:
            # Only keep completed if Celery already enriched (not instant stub)
            if not (existing.output_data or {}).get("instant"):
                return
        AgentAction.objects.update_or_create(
            user=user,
            action_type=action_type,
            defaults={
                "agent_type": agent_type,
                "description": description,
                "status": AgentAction.ActionStatus.STARTED,
                "output_data": {"instant_preview": True, "posts_preview": post_count},
                "error_message": "",
            },
        )

    _mark_complete(
        "research",
        "research",
        f"Mapped starter angles for {company}",
        stub_research,
    )
    _mark_complete(
        "seeds",
        "strategist",
        "Planned your first 3 post angles",
        {"seed_count": len(opportunity_briefs), "instant": True},
    )

    # Content stays STARTED so Celery enrichment is not skipped.
    if post_count:
        _mark_pending(
            "content",
            "create",
            f"{post_count} draft{'s' if post_count != 1 else ''} ready — sharpening copy…",
        )

    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=user, date=today).first()
    if not brief:
        summary = (
            f"Welcome to Kova, {company}. "
            f"{'Your first drafts are ready in Studio — written as real posts, not a bio dump. ' if post_count else ''}"
            f"Next: review a draft, connect Instagram/Facebook/WhatsApp, then approve."
        )
        brief = DailyBrief.objects.create(
            user=user,
            date=today,
            summary=summary,
            trending_topics=stub_research["trending_topics"],
            suggested_posts=[
                {"idea": b["title"], "reasoning": b["description"], "platform": "instagram"}
                for b in opportunity_briefs[:3]
            ],
            performance_summary={
                "highlight": f"Approve one post to teach Kova how {company} sounds.",
                "agent_summary": "Research and Create are active on your brand.",
            },
            agent_activity=[],
            posts_pending=post_count,
        )

    _mark_complete(
        "brief",
        "strategist",
        "Welcome brief ready",
        {"brief_id": str(brief.pk), "instant": True},
    )

    # Do NOT record intelligence_completed here — Celery owns the real finish line.
    try:
        profile.record_onboarding_step("intelligence_preview_ready")
    except Exception:
        logger.exception("record intelligence_preview_ready failed for %s", user.email)

    return bool(post_count or brief)


def finish_onboarding(user, *, skipped_platform_connect=False):
    """
    Mark onboarding complete, start trial, bootstrap email, fire intelligence chain.
    Platform connect is optional — publishing can be gated separately.
    """
    from apps.create.agents.models import AgentConfig
    from apps.create.agents.onboarding_tasks import run_onboarding_intelligence
    from apps.messaging.emails.automation import bootstrap_email_automation
    from apps.messaging.emails.tasks import send_welcome_email
    from apps.core.utils import fire_task

    profile = user.profile

    user.onboarding_completed = True
    user.save(update_fields=["onboarding_completed"])
    profile.record_onboarding_step("step_4_completed")
    if skipped_platform_connect:
        profile.record_onboarding_step("platform_connect_deferred")

    for agent_type in AgentConfig.AgentType.values:
        AgentConfig.objects.get_or_create(
            user=user,
            agent_type=agent_type,
            defaults={"is_active": True},
        )

    if not profile.trial_ends_at:
        from django.conf import settings

        trial_days = getattr(settings, "MPESA_TRIAL_DAYS", 7)
        profile.trial_ends_at = timezone.now() + timedelta(days=trial_days)
        profile.current_period_end = profile.trial_ends_at
        profile.subscription_status = "trialing"
        profile.save(update_fields=["trial_ends_at", "current_period_end", "subscription_status"])

    fire_task(send_welcome_email, str(user.pk))
    bootstrap_email_automation(user)

    profile.onboarding_intelligence_started_at = timezone.now()
    profile.save(update_fields=["onboarding_intelligence_started_at"])
    profile.record_onboarding_step("intelligence_started")
    ensure_instant_onboarding_wow(user)

    # First Business Report — the "Kova already understands my business" moment.
    try:
        from apps.core.accounts.first_business_report import cache_first_business_report
        cache_first_business_report(user)
    except Exception:
        logger.exception("First Business Report generation failed for %s", user.email)

    fire_task(run_onboarding_intelligence, str(user.pk))

    logger.info(
        "Onboarding finished for %s (platform_deferred=%s)",
        user.email,
        skipped_platform_connect,
    )
