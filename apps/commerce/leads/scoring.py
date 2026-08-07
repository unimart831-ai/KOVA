"""
Composite Lead Scoring Engine — scores leads 0-100 using all available signals.

Signals aggregated:
- Social engagement (comments, DMs, mentions on seller's posts)
- Commerce behavior (purchases, amounts, frequency)
- Email engagement (opens, clicks, replies)
- WhatsApp activity (messages, commerce interactions)
- Website/pixel activity (page views, form visits)
- Booking history (appointments, completion rate)
- Recency (time since last activity)
- Profile completeness (has phone, real email, name)

The score drives:
- Priority assignment (HIGH/MEDIUM/LOW)
- Temperature updates (HOT/WARM/COLD)
- Nurture channel selection
- Which leads surface in Daily Brief
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


class ScoreWeights:
    """Configurable weights for each signal category."""
    SOCIAL_ENGAGEMENT = 15      # max 15 points
    COMMERCE_BEHAVIOR = 25      # max 25 points (buyers are most valuable)
    EMAIL_ENGAGEMENT = 10       # max 10 points
    WHATSAPP_ACTIVITY = 15      # max 15 points
    WEBSITE_ACTIVITY = 10       # max 10 points
    BOOKING_HISTORY = 10        # max 10 points
    RECENCY = 10                # max 10 points
    PROFILE_COMPLETENESS = 5    # max 5 points


def compute_composite_score(lead) -> int:
    """
    Compute a composite lead score (0-100) from all available signals.
    Returns the integer score.
    """
    score = 0

    score += _score_social_engagement(lead)
    score += _score_commerce_behavior(lead)
    score += _score_email_engagement(lead)
    score += _score_whatsapp_activity(lead)
    score += _score_website_activity(lead)
    score += _score_booking_history(lead)
    score += _score_recency(lead)
    score += _score_profile_completeness(lead)

    return min(100, max(0, score))


def score_and_update_lead(lead) -> int:
    """Compute score, update priority/temperature, and save."""
    score = compute_composite_score(lead)

    from apps.commerce.leads.models import Lead

    if score >= 70:
        lead.priority = Lead.Priority.HIGH
    elif score >= 35:
        lead.priority = Lead.Priority.MEDIUM
    else:
        lead.priority = Lead.Priority.LOW

    if score >= 60:
        lead.temperature = Lead.Temperature.HOT
    elif score >= 30:
        lead.temperature = Lead.Temperature.WARM
    else:
        lead.temperature = Lead.Temperature.COLD

    metadata = lead.metadata or {}
    metadata["composite_score"] = score
    metadata["scored_at"] = timezone.now().isoformat()
    lead.metadata = metadata

    lead.save(update_fields=["priority", "temperature", "metadata", "last_activity_at"])
    return score


def _score_social_engagement(lead) -> int:
    """Score based on social interactions (comments, DMs, mentions)."""
    from apps.commerce.leads.models import LeadActivity

    social_activities = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.SOCIAL_INTERACTION
    ).count()

    source_bonus = 3 if lead.source_type in ("social_dm", "social_comment") else 0

    # Scale: 0 activities=0, 1=5, 2=8, 3+=12, plus source bonus capped at 15
    if social_activities >= 3:
        return min(12 + source_bonus, ScoreWeights.SOCIAL_ENGAGEMENT)
    elif social_activities >= 2:
        return min(8 + source_bonus, ScoreWeights.SOCIAL_ENGAGEMENT)
    elif social_activities >= 1:
        return min(5 + source_bonus, ScoreWeights.SOCIAL_ENGAGEMENT)
    return min(source_bonus, ScoreWeights.SOCIAL_ENGAGEMENT)


def _score_commerce_behavior(lead) -> int:
    """Score based on purchase history."""
    from apps.commerce.leads.models import LeadActivity

    purchases = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.COMMERCE_PURCHASE
    )
    purchase_count = purchases.count()

    if purchase_count == 0:
        if lead.source_type == "commerce_purchase":
            return 15
        return 0

    total_spend = Decimal("0")
    for activity in purchases.only("metadata")[:20]:
        try:
            amount = Decimal(str(activity.metadata.get("amount", 0)))
            total_spend += amount
        except Exception:
            pass

    score = min(purchase_count * 7, 22)

    # Spend bonus: >5000 KES = +3
    if total_spend > 5000:
        score += 3

    return min(score, ScoreWeights.COMMERCE_BEHAVIOR)


def _score_email_engagement(lead) -> int:
    """Score based on email opens and clicks."""
    from apps.commerce.leads.models import LeadActivity

    opens = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.EMAIL_OPENED
    ).count()
    clicks = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.EMAIL_CLICKED
    ).count()

    score = min(opens * 2, 4) + min(clicks * 4, 6)
    return min(score, ScoreWeights.EMAIL_ENGAGEMENT)


def _score_whatsapp_activity(lead) -> int:
    """Score based on WhatsApp interactions."""
    from apps.commerce.leads.models import LeadActivity

    wa_activities = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.WHATSAPP_SENT
    ).count()

    source_bonus = 5 if lead.source_platform == "whatsapp" else 0

    activity_score = min(wa_activities * 3, 10)
    return min(activity_score + source_bonus, ScoreWeights.WHATSAPP_ACTIVITY)


def _score_website_activity(lead) -> int:
    """Score based on pixel/website events."""
    metadata = lead.metadata or {}
    page_views = metadata.get("page_views", 0)
    form_views = metadata.get("form_views", 0)

    score = min(page_views, 5) + min(form_views * 3, 5)
    return min(score, ScoreWeights.WEBSITE_ACTIVITY)


def _score_booking_history(lead) -> int:
    """Score based on booking activities."""
    from apps.commerce.leads.models import LeadActivity

    bookings_made = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.BOOKING_MADE
    ).count()
    bookings_completed = lead.activities.filter(
        activity_type=LeadActivity.ActivityType.BOOKING_COMPLETED
    ).count()

    score = bookings_made * 4 + bookings_completed * 3
    return min(score, ScoreWeights.BOOKING_HISTORY)


def _score_recency(lead) -> int:
    """Score based on how recently the lead was active."""
    now = timezone.now()
    last_activity = lead.last_activity_at or lead.first_seen_at

    if not last_activity:
        return 0

    days_ago = (now - last_activity).days

    if days_ago <= 1:
        return ScoreWeights.RECENCY  # 10
    elif days_ago <= 3:
        return 8
    elif days_ago <= 7:
        return 6
    elif days_ago <= 14:
        return 4
    elif days_ago <= 30:
        return 2
    return 0


def _score_profile_completeness(lead) -> int:
    """Score based on how much we know about the lead."""
    score = 0
    if lead.name and lead.name.strip():
        score += 1
    if lead.phone and lead.phone.strip():
        score += 2
    if lead.email and "@kova.page" not in lead.email:
        score += 2
    return min(score, ScoreWeights.PROFILE_COMPLETENESS)
