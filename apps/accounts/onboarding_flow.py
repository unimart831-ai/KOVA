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


def seed_onboarding_preview_posts(user) -> int:
    """Create instant draft posts from user voice examples (visible before Celery)."""
    from apps.content.models import Post

    profile = user.profile
    examples = [e.strip() for e in (profile.brand_voice_examples or []) if e and str(e).strip()]
    if not examples and (profile.brand_voice or "").strip():
        examples = [(profile.brand_voice or "").strip()[:500]]

    if not examples:
        return 0
    if Post.objects.filter(user=user, generated_by_agent="onboarding_seed").exists():
        return 0

    created = 0
    for text in examples[:3]:
        Post.objects.create(
            user=user,
            content_text=text[:2200],
            status=Post.Status.PENDING_APPROVAL,
            generated_by_agent="onboarding_seed",
            platform="instagram",
        )
        created += 1
    return created


def ensure_instant_onboarding_wow(user) -> bool:
    """
    Sync bootstrap so the WOW screen shows posts + brief immediately.
    Celery may enrich later; this must never block on LLM.
    Returns True when instant value is ready (posts or welcome brief).
    """
    from apps.agents.models import AgentAction
    from apps.agents.onboarding_tasks import ONBOARDING_STEPS
    from apps.briefs.models import DailyBrief
    from apps.content.models import Post

    profile = user.profile
    company = (profile.company_name or "your business").strip()
    brand_snippet = (profile.brand_voice or "").strip()
    brand_preview = brand_snippet[:160] + ("…" if len(brand_snippet) > 160 else "")

    seed_onboarding_preview_posts(user)

    post_count = Post.objects.filter(
        user=user,
        status__in=[Post.Status.PENDING_APPROVAL, Post.Status.DRAFT],
    ).count()

    opportunity_briefs = [
        {
            "title": f"Introduce {company}",
            "description": brand_preview or f"Who {company} is and what you offer",
            "why_now": "First impression on social",
        },
        {
            "title": f"A day in the life of {company}",
            "description": "Show customers what makes you different",
            "why_now": "Build trust early",
        },
    ]
    if brand_snippet:
        opportunity_briefs.insert(0, {
            "title": "Your brand story",
            "description": brand_preview,
            "why_now": "From what you told Kova",
        })

    stub_research = {
        "trending_topics": [
            {
                "topic": f"Content ideas for {company}",
                "suggested_angle": "Lead with your own words — Kova matches your voice",
            }
        ],
        "opportunity_briefs": opportunity_briefs[:3],
        "source": "brand_description",
    }

    completed = AgentAction.ActionStatus.COMPLETED

    def _mark_complete(step_key: str, agent_type: str, description: str, output_data: dict) -> None:
        action_type = ONBOARDING_STEPS[step_key]
        existing = AgentAction.objects.filter(user=user, action_type=action_type).first()
        if existing:
            if existing.status == completed:
                return
            if existing.status == AgentAction.ActionStatus.RUNNING:
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

    _mark_complete(
        "research",
        "research",
        "Starter plan from your profile",
        stub_research,
    )
    _mark_complete(
        "seeds",
        "strategist",
        "Planned starter campaign angles",
        {"seed_count": len(opportunity_briefs), "instant": True},
    )
    if post_count:
        _mark_complete(
            "content",
            "create",
            "Draft posts ready in Studio",
            {"posts_created": post_count, "instant": True},
        )

    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=user, date=today).first()
    if not brief:
        summary = (
            f"Welcome to Kova, {company}! "
            f"{'Your draft posts are waiting in Studio — written in your voice. ' if post_count else ''}"
            f"Kova is learning from what you told us and will sharpen every post as you approve content."
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
                "highlight": f"You're set up. Approve your first post to train the agents on {company}'s voice.",
                "agent_summary": "Research, Create, and Strategist agents are active on your brand.",
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

    try:
        profile.record_onboarding_step("intelligence_completed")
    except Exception:
        logger.exception("record intelligence_completed failed for %s", user.email)

    return bool(post_count or brief)


def finish_onboarding(user, *, skipped_platform_connect=False):
    """
    Mark onboarding complete, start trial, bootstrap email, fire intelligence chain.
    Platform connect is optional — publishing can be gated separately.
    """
    from apps.agents.models import AgentConfig
    from apps.agents.onboarding_tasks import run_onboarding_intelligence
    from apps.emails.automation import bootstrap_email_automation
    from apps.emails.tasks import send_welcome_email
    from apps.utils import fire_task

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

    send_welcome_email.delay(str(user.pk))
    bootstrap_email_automation(user)

    if getattr(profile, "business_model", "") == "service":
        from apps.bookings.service_setup import bootstrap_service_booking_link
        try:
            bootstrap_service_booking_link(user)
        except Exception:
            logger.exception("bootstrap_service_booking_link failed for %s", user.email)

    profile.onboarding_intelligence_started_at = timezone.now()
    profile.save(update_fields=["onboarding_intelligence_started_at"])
    profile.record_onboarding_step("intelligence_started")
    ensure_instant_onboarding_wow(user)
    fire_task(run_onboarding_intelligence, str(user.pk))

    logger.info(
        "Onboarding finished for %s (platform_deferred=%s)",
        user.email,
        skipped_platform_connect,
    )
