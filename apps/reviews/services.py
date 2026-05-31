"""Core service functions for the review loop.

Split out of views/tasks so unit tests can exercise the logic without
spinning up Celery or full request lifecycle.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from apps.reviews.models import ReviewRequest
from apps.reviews.sentiment import classify

logger = logging.getLogger(__name__)


def send_review_request(req: ReviewRequest) -> bool:
    """Fire the WhatsApp or email outreach. Returns True if sent."""
    business = _business_name(req)
    customer = req.customer_name or "there"
    message = _build_message(business, customer, req)

    if req.channel == ReviewRequest.Channel.WHATSAPP:
        ok = _try_whatsapp(req.customer_phone, message, user=req.user)
    else:
        ok = _try_email(req.customer_email, business, message)

    now = timezone.now()
    if ok:
        ReviewRequest.objects.filter(pk=req.pk).update(
            status=ReviewRequest.Status.SENT,
            sent_at=now,
        )
    else:
        # Try the fallback channel
        if req.channel == ReviewRequest.Channel.WHATSAPP and req.customer_email:
            if _try_email(req.customer_email, business, message):
                ReviewRequest.objects.filter(pk=req.pk).update(
                    status=ReviewRequest.Status.SENT,
                    sent_at=now,
                    channel=ReviewRequest.Channel.EMAIL,
                )
                return True
        ReviewRequest.objects.filter(pk=req.pk).update(
            status=ReviewRequest.Status.FAILED,
            failure_reason="Outreach failed (no working channel).",
        )
    return ok


def process_response(req: ReviewRequest, response_text: str) -> ReviewRequest:
    """Customer replied to the review request — classify + branch."""
    label, score = classify(response_text)
    req.response_text = response_text
    req.sentiment = label
    req.sentiment_score = score
    req.responded_at = timezone.now()
    req.status = ReviewRequest.Status.RESPONDED
    req.save(update_fields=[
        "response_text", "sentiment", "sentiment_score",
        "responded_at", "status", "updated_at",
    ])

    if label == ReviewRequest.Sentiment.POSITIVE:
        _create_content_seed(req)
    elif label == ReviewRequest.Sentiment.NEGATIVE:
        _flag_for_brief(req)
    return req


# ── Helpers ────────────────────────────────────────────────────────────────


def _business_name(req: ReviewRequest) -> str:
    profile = getattr(req.user, "profile", None)
    return (profile.company_name if profile else "") or "us"


def _build_message(business: str, customer: str, req: ReviewRequest) -> str:
    """The outreach copy. Short, warm, specific to what they did."""
    what = ""
    if req.booking_id:
        what = f" after your {req.booking.service_name}"
    return (
        f"Hi {customer}! Quick favour — could you share a few words about "
        f"your experience with {business}{what}? "
        f"Even one line helps a lot. Asante! 🙏"
    )


def _try_whatsapp(to: str, message: str, user=None) -> bool:
    if not to:
        return False
    try:
        from apps.whatsapp.services import send_text_message
        send_text_message(to=to, body=message, user=user)
        return True
    except Exception as e:
        logger.info("WhatsApp send unavailable (%s) — would have sent to %s", e, to)
        return False


def _try_email(to: str, subject: str, message: str) -> bool:
    if not to:
        return False
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject=f"Quick favour from {subject}",
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@kova.ai"),
            recipient_list=[to],
            fail_silently=True,
        )
        return True
    except Exception as e:
        logger.warning("Email send failed: %s", e)
        return False


def _create_content_seed(req: ReviewRequest):
    """Positive review → ContentSeed the Create Agent can turn into a post."""
    if req.content_seed_id:
        return
    try:
        from apps.content.models import ContentSeed
    except Exception:
        return
    idea = (
        f"Customer testimonial — \"{req.response_text.strip()[:280]}\" "
        f"— from {req.customer_name or 'a customer'}"
    )
    seed = ContentSeed.objects.create(
        user=req.user,
        idea=idea,
        notes=(
            "Auto-created from a positive review response. Use as social "
            "proof — quote in carousel, testimonial graphic, or short post."
        ),
    )
    ReviewRequest.objects.filter(pk=req.pk).update(content_seed=seed)


def _flag_for_brief(req: ReviewRequest):
    """Negative review → surface in Daily Brief for owner attention."""
    ReviewRequest.objects.filter(pk=req.pk).update(escalated_in_brief=True)
