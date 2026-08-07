"""Celery tasks for Growth Partners — commissions and milestones."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.utils.locks import single_run

logger = logging.getLogger(__name__)


def _previous_month_period(today: date | None = None):
    today = today or timezone.now().date()
    first_of_month = today.replace(day=1)
    period_end = first_of_month - timedelta(days=1)
    period_start = period_end.replace(day=1)
    return period_start, period_end


@shared_task(name="partners.calculate_monthly_commissions")
@single_run("partners.calculate_monthly_commissions", timeout=30 * 60)
def calculate_monthly_commissions():
    """
    Create Commission rows for the previous calendar month.

    Runs on the 1st — one row per active referral × plan revenue × commission rate.
    """
    from apps.core.billing.models import get_plan_limits
    from apps.core.partners.models import Commission, Partner, Referral

    period_start, period_end = _previous_month_period()
    created_count = 0
    partners_updated = 0

    partners = Partner.objects.filter(is_active=True).prefetch_related("referrals")
    for partner in partners:
        partner.recalculate_tier()
        rate = partner.commission_rate
        partner_total = Decimal("0.00")

        active_referrals = partner.referrals.filter(
            is_active=True,
            is_flagged=False,
            activated_at__isnull=False,
        )

        for referral in active_referrals:
            if not referral.is_commission_active:
                continue

            plan = referral.current_plan or getattr(
                referral.referred_user.profile, "plan", "starter"
            )
            revenue = Decimal(str(get_plan_limits(plan).get("price_kes", 0)))
            amount = (revenue * rate).quantize(Decimal("0.01"))

            if amount <= 0:
                continue

            _, created = Commission.objects.get_or_create(
                partner=partner,
                referral=referral,
                period_start=period_start,
                defaults={
                    "period_end": period_end,
                    "client_revenue_kes": revenue,
                    "commission_rate": rate,
                    "amount_kes": amount,
                    "status": Commission.Status.PENDING,
                },
            )
            if created:
                created_count += 1
                partner_total += amount

        if partner_total > 0:
            Partner.objects.filter(pk=partner.pk).update(
                pending_payout_kes=F("pending_payout_kes") + partner_total,
            )
            partners_updated += 1

    logger.info(
        "Monthly commissions: period=%s..%s created=%s partners=%s",
        period_start, period_end, created_count, partners_updated,
    )
    return {
        "period_start": str(period_start),
        "period_end": str(period_end),
        "commissions_created": created_count,
        "partners_updated": partners_updated,
    }


@shared_task(name="partners.check_partner_milestones")
@single_run("partners.check_partner_milestones", timeout=20 * 60)
def check_partner_milestones():
    """Award milestone bonuses when active client thresholds are reached."""
    from apps.core.partners.models import MILESTONE_BONUSES, MilestoneAward, Partner

    awarded = 0
    for partner in Partner.objects.filter(is_active=True):
        active_count = partner.active_referrals_count
        for clients_required, bonus_kes, label, extras in MILESTONE_BONUSES:
            if active_count < clients_required:
                continue
            _, created = MilestoneAward.objects.get_or_create(
                partner=partner,
                clients_required=clients_required,
                defaults={
                    "label": label,
                    "bonus_kes": Decimal(str(bonus_kes)),
                    "extras": extras,
                },
            )
            if not created:
                continue

            Partner.objects.filter(pk=partner.pk).update(
                pending_payout_kes=F("pending_payout_kes") + Decimal(str(bonus_kes)),
            )
            awarded += 1

            try:
                from apps.messaging.emails.tasks import send_partner_milestone_email
                send_partner_milestone_email.delay(
                    str(partner.user.pk),
                    label,
                    bonus_kes,
                    extras,
                )
            except Exception:
                logger.exception(
                    "Failed to queue milestone email for partner %s", partner.referral_code
                )

    logger.info("Milestone check complete: %s new awards", awarded)
    return {"awards_created": awarded}
