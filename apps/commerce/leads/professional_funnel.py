"""Professional consultation lead pipeline automation."""

from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def process_professional_consult_lead(lead, user, *, interaction=None, booking=None):
    """
    Tag, prioritize, and nurture consultation leads for professional businesses.
    Called after engage booking intent or confirmed bookings.
    """
    profile = getattr(user, "profile", None)
    if not profile or getattr(profile, "business_model", "") != "professional":
        return lead

    from apps.commerce.leads.models import Lead, LeadActivity

    meta = dict(lead.metadata or {})
    stage = "inquiry"
    if interaction and getattr(interaction, "ai_intent", "") == "booking":
        stage = "booking_intent"
    elif booking:
        stage = "booked"

    meta["consult_funnel_stage"] = stage
    meta["consult_funnel_updated"] = timezone.now().isoformat()
    meta["pipeline"] = "professional_consult"
    if interaction and meta.get("booking_url"):
        meta["suggested_owner_action"] = meta.get(
            "suggested_owner_action",
            "Reply with booking link or text BOOK on WhatsApp",
        )

    lead.metadata = meta
    if lead.temperature != Lead.Temperature.HOT:
        lead.temperature = Lead.Temperature.HOT
    lead.last_activity_at = timezone.now()
    lead.save(update_fields=["metadata", "temperature", "last_activity_at", "updated_at"])

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.NOTE_ADDED,
        description=f"Consultation funnel: {stage.replace('_', ' ')}",
        metadata={"stage": stage, "pipeline": "professional_consult"},
    )

    try:
        from apps.commerce.leads.defaults import ensure_professional_nurture_sequences
        from apps.commerce.leads.tasks import enroll_lead_in_sequences

        ensure_professional_nurture_sequences(user)
        from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads

        if should_auto_enroll_leads(user):
            enroll_lead_in_sequences(lead)
    except Exception:
        logger.exception("Professional consult funnel nurture failed for lead %s", lead.pk)

    return lead


CONSULT_FUNNEL_STAGES = {
    "inquiry": "Inquiry",
    "booking_intent": "Booking intent",
    "booked": "Consult booked",
}


def consult_funnel_stage_label(lead) -> str:
    """Human label for professional consult pipeline stage, or empty string."""
    meta = getattr(lead, "metadata", None) or {}
    if meta.get("pipeline") != "professional_consult":
        return ""
    stage = meta.get("consult_funnel_stage", "")
    return CONSULT_FUNNEL_STAGES.get(stage, stage.replace("_", " ").title() if stage else "")
