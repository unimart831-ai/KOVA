"""
Default nurture sequences for new REACH users.
"""
from __future__ import annotations

WELCOME_SEQUENCE_NAME = "Welcome new leads"
WINBACK_SEQUENCE_NAME = "Win back stale leads"


def ensure_default_nurture_sequences(user) -> None:
    """
    Ensure per-user default welcome + stale win-back sequences exist.
    Idempotent — safe to call on every new lead.
    """
    from apps.leads.models import NurtureSequence, NurtureStep

    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "business_model", "") == "professional":
        ensure_professional_nurture_sequences(user)

    if not NurtureSequence.objects.filter(user=user, name=WELCOME_SEQUENCE_NAME).exists():
        welcome = NurtureSequence.objects.create(
            user=user,
            name=WELCOME_SEQUENCE_NAME,
            trigger=NurtureSequence.Trigger.ALL_NEW,
            is_active=True,
        )
        NurtureStep.objects.create(
            sequence=welcome,
            order=0,
            delay_hours=0,
            action_type=NurtureStep.ActionType.SEND_WHATSAPP,
            email_subject="Thanks for connecting",
            email_body=(
                "Hi! Thanks for reaching out. We're glad you're here — "
                "reply to this message anytime if you have questions."
            ),
        )
        NurtureStep.objects.create(
            sequence=welcome,
            order=1,
            delay_hours=48,
            action_type=NurtureStep.ActionType.SEND_EMAIL,
            email_subject="A quick hello from us",
            email_body=(
                "Hi,\n\nJust checking in to see if we can help with anything. "
                "Feel free to reply to this email.\n\nBest regards"
            ),
        )

    if NurtureSequence.objects.filter(user=user, name=WINBACK_SEQUENCE_NAME).exists():
        return

    winback = NurtureSequence.objects.create(
        user=user,
        name=WINBACK_SEQUENCE_NAME,
        trigger=NurtureSequence.Trigger.STALE_WINBACK,
        is_active=True,
    )
    NurtureStep.objects.create(
        sequence=winback,
        order=0,
        delay_hours=0,
        action_type=NurtureStep.ActionType.SEND_WHATSAPP,
        email_subject="We miss you",
        email_body=(
            "Hi! It's been a while — we'd love to hear from you again. "
            "Reply if you'd like to pick up where we left off."
        ),
    )


CONSULTATION_SEQUENCE_NAME = "Consultation follow-up"


def ensure_professional_nurture_sequences(user) -> None:
    """Booking-intent follow-up for professional businesses."""
    from apps.leads.models import NurtureSequence, NurtureStep

    if NurtureSequence.objects.filter(user=user, name=CONSULTATION_SEQUENCE_NAME).exists():
        return

    seq = NurtureSequence.objects.create(
        user=user,
        name=CONSULTATION_SEQUENCE_NAME,
        trigger=NurtureSequence.Trigger.FROM_BOOKING_INTENT,
        is_active=True,
    )
    NurtureStep.objects.create(
        sequence=seq,
        order=0,
        delay_hours=0,
        action_type=NurtureStep.ActionType.SEND_WHATSAPP,
        email_subject="Thanks for your interest",
        email_body=(
            "Hi! Thanks for asking about a consultation. "
            "Reply BOOK anytime and we'll send your booking link."
        ),
    )
    NurtureStep.objects.create(
        sequence=seq,
        order=1,
        delay_hours=24,
        action_type=NurtureStep.ActionType.SEND_EMAIL,
        email_subject="Book your consultation",
        email_body=(
            "Hi,\n\nFollowing up on your consultation request. "
            "Pick a time that works for you — we're ready when you are.\n\n"
            "Best regards"
        ),
    )
    NurtureStep.objects.create(
        sequence=seq,
        order=2,
        delay_hours=72,
        action_type=NurtureStep.ActionType.SEND_WHATSAPP,
        email_subject="Still interested?",
        email_body=(
            "Quick check-in — still happy to talk through your project. "
            "Reply here or text BOOK on WhatsApp."
        ),
    )
