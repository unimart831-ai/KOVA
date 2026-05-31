"""Wire subscription payments to Growth Partner referrals."""

from __future__ import annotations

import calendar
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def _add_months(dt, months: int):
    """Return dt shifted forward by ``months`` calendar months."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def record_referral_payment(user, plan_tier: str, revenue_kes: Decimal | None = None) -> bool:
    """
    Increment referral progress when a referred user completes a paid month.

    Called from M-Pesa activation and Stripe invoice.paid handlers.
    Returns True if a referral was updated.
    """
    from apps.billing.models import get_plan_limits
    from apps.partners.models import Referral

    try:
        referral = (
            Referral.objects.select_for_update()
            .select_related("partner")
            .get(referred_user=user, is_active=True, is_flagged=False)
        )
    except Referral.DoesNotExist:
        return False

    now = timezone.now()
    limits = get_plan_limits(plan_tier or user.profile.plan)
    if revenue_kes is None:
        revenue_kes = Decimal(str(limits.get("price_kes", 0)))

    # Skip duplicate billing events within the same calendar month
    if referral.last_payment_at and referral.last_payment_at.year == now.year and referral.last_payment_at.month == now.month:
        return False

    referral.current_plan = plan_tier or user.profile.plan
    referral.consecutive_paid_months += 1
    referral.last_payment_at = now

    if referral.consecutive_paid_months >= 2 and not referral.activated_at:
        referral.activated_at = now
        referral.commission_expires_at = _add_months(now, 24)

    referral.save(update_fields=[
        "current_plan",
        "consecutive_paid_months",
        "last_payment_at",
        "activated_at",
        "commission_expires_at",
    ])

    referral.partner.recalculate_tier()
    logger.info(
        "Referral payment recorded: %s → %s (months=%s, plan=%s)",
        user.email,
        referral.partner.referral_code,
        referral.consecutive_paid_months,
        referral.current_plan,
    )
    return True


def record_referral_payment_safe(user, plan_tier: str, revenue_kes: Decimal | None = None) -> bool:
    """Non-blocking wrapper — never raises into billing flows."""
    try:
        with transaction.atomic():
            return record_referral_payment(user, plan_tier, revenue_kes)
    except Exception:
        logger.exception("Failed to record referral payment for user %s", getattr(user, "email", user))
        return False
