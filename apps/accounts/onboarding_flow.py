"""Shared onboarding completion and URL-inference helpers."""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

SETUP_TOTAL_STEPS = 5


def setup_step_for_wizard(step: int) -> int:
    """Map wizard step (1–3) to global setup progress (2–4)."""
    return step + 1


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
    _set_if_empty("brand_voice", data.get("brand_voice"))
    _set_if_empty("target_audience", data.get("target_audience"))
    if data.get("content_pillars"):
        _set_if_empty("content_pillars", data["content_pillars"])
    if data.get("tone_attributes"):
        _set_if_empty("tone_attributes", data["tone_attributes"])
    if data.get("key_offerings"):
        _set_if_empty("key_offerings", data["key_offerings"])

    if updated:
        profile.save()
    return updated


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

    profile.onboarding_intelligence_started_at = timezone.now()
    profile.save(update_fields=["onboarding_intelligence_started_at"])
    profile.record_onboarding_step("intelligence_started")
    fire_task(run_onboarding_intelligence, str(user.pk))

    logger.info(
        "Onboarding finished for %s (platform_deferred=%s)",
        user.email,
        skipped_platform_connect,
    )
