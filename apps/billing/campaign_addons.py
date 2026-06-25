"""
Campaign add-on packs — M-Pesa checkout and quota crediting.

Add-ons stack on the base monthly campaign quota via profile.seed_monthly_bonus.
"""

from __future__ import annotations

import logging

from django.db import transaction

from apps.billing.models import (
    CAMPAIGN_ADDON_PACKS,
    CampaignAddonPurchase,
    ContentSeedQuotaLog,
    MpesaPayment,
)

logger = logging.getLogger(__name__)


def get_addon_pack(pack_id: str) -> dict | None:
    """Return pack config or None if invalid."""
    pack = CAMPAIGN_ADDON_PACKS.get(pack_id)
    return pack.copy() if pack else None


def user_can_purchase_addons(user) -> tuple[bool, str]:
    """Active or trialing subscribers may buy campaign add-ons."""
    profile = getattr(user, "profile", None)
    if not profile:
        return False, "Account profile not found."
    if profile.subscription_status not in ("active", "trialing"):
        return False, "Subscribe to Kova first, then you can add extra campaigns."
    return True, ""


@transaction.atomic
def apply_campaign_addon_purchase(payment: MpesaPayment) -> CampaignAddonPurchase:
    """
    Credit purchased campaigns to seed_monthly_bonus after successful M-Pesa payment.

    Idempotent: returns existing purchase if already applied for this payment.
    """
    if not payment.is_campaign_addon:
        raise ValueError("Payment is not a campaign add-on purchase.")

    existing = CampaignAddonPurchase.objects.filter(mpesa_payment=payment).first()
    if existing:
        return existing

    pack = get_addon_pack(payment.addon_pack_id)
    if not pack:
        raise ValueError(f"Unknown add-on pack: {payment.addon_pack_id}")

    user = payment.user
    profile = user.profile
    bonus_before = int(profile.seed_monthly_bonus or 0)
    campaigns = int(pack["campaigns"])

    from apps.billing.enforcement import get_seed_usage
    from apps.billing.campaign_renewal import apply_addon_purchase_bonus

    usage_before = get_seed_usage(user)
    apply_addon_purchase_bonus(profile, pack)
    profile.refresh_from_db()
    bonus_after = int(profile.seed_monthly_bonus or 0)

    usage_after = get_seed_usage(user)
    ContentSeedQuotaLog.objects.create(
        user=user,
        admin=None,
        action=ContentSeedQuotaLog.Action.ADDON_PURCHASE,
        reason=f"M-Pesa add-on: {pack['label']} (receipt {payment.receipt_number or payment.pk})",
        used_before=usage_before["used"],
        max_before=usage_before["max"],
        remaining_before=usage_before["remaining"],
        plan_label=usage_before["plan_label"],
        metadata={
            "pack_id": payment.addon_pack_id,
            "campaigns": campaigns,
            "bonus_before": bonus_before,
            "bonus_after": bonus_after,
            "max_after": usage_after["max"],
            "mpesa_payment_id": str(payment.pk),
            "recurring": bool(pack.get("recurring")),
        },
    )

    purchase = CampaignAddonPurchase.objects.create(
        user=user,
        mpesa_payment=payment,
        pack_id=payment.addon_pack_id,
        campaigns_granted=campaigns,
        bonus_before=bonus_before,
        bonus_after=bonus_after,
    )

    logger.info(
        "Campaign add-on applied: user=%s pack=%s +%d bonus=%d→%d",
        user.email,
        payment.addon_pack_id,
        campaigns,
        bonus_before,
        bonus_after,
    )
    return purchase
