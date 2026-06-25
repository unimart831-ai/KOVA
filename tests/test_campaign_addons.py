"""Tests for campaign add-on M-Pesa checkout and quota crediting."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.billing.campaign_addons import apply_campaign_addon_purchase, user_can_purchase_addons
from apps.billing.enforcement import get_seed_usage
from apps.billing.models import CampaignAddonPurchase, ContentSeedQuotaLog, MpesaPayment


@pytest.mark.django_db
class TestCampaignAddonAccess:
    def test_active_subscriber_can_purchase(self, user):
        profile = user.profile
        profile.subscription_status = "active"
        profile.plan = "kova"
        profile.save(update_fields=["subscription_status", "plan"])

        allowed, _ = user_can_purchase_addons(user)
        assert allowed is True

    def test_free_user_cannot_purchase(self, user):
        profile = user.profile
        profile.subscription_status = "none"
        profile.save(update_fields=["subscription_status"])

        allowed, msg = user_can_purchase_addons(user)
        assert allowed is False
        assert "Subscribe" in msg


@pytest.mark.django_db
class TestApplyCampaignAddon:
    def test_boost_increments_bonus(self, user):
        profile = user.profile
        profile.plan = "kova"
        profile.subscription_status = "active"
        profile.seed_monthly_bonus = 0
        profile.save(update_fields=["plan", "subscription_status", "seed_monthly_bonus"])

        payment = MpesaPayment.objects.create(
            user=user,
            phone_number="254712345678",
            amount=450,
            plan_tier="kova",
            payment_kind=MpesaPayment.PaymentKind.CAMPAIGN_ADDON,
            addon_pack_id="boost",
            merchant_request_id="mr_boost",
            checkout_request_id="cr_boost",
            status=MpesaPayment.Status.COMPLETED,
            completed_at=timezone.now(),
            receipt_number="ABC123",
        )

        purchase = apply_campaign_addon_purchase(payment)
        profile.refresh_from_db()

        assert purchase.campaigns_granted == 10
        assert profile.seed_monthly_bonus == 10
        usage = get_seed_usage(user)
        assert usage["max"] == 40  # 30 base + 10 boost
        assert usage["bonus"] == 10

        log = ContentSeedQuotaLog.objects.filter(
            user=user,
            action=ContentSeedQuotaLog.Action.ADDON_PURCHASE,
        ).first()
        assert log is not None
        assert log.metadata["pack_id"] == "boost"

    def test_idempotent_on_same_payment(self, user):
        profile = user.profile
        profile.subscription_status = "active"
        profile.seed_monthly_bonus = 5
        profile.burst_campaign_bonus = 5
        profile.save(update_fields=["subscription_status", "seed_monthly_bonus", "burst_campaign_bonus"])

        payment = MpesaPayment.objects.create(
            user=user,
            phone_number="254712345678",
            amount=250,
            plan_tier="kova",
            payment_kind=MpesaPayment.PaymentKind.CAMPAIGN_ADDON,
            addon_pack_id="burst",
            merchant_request_id="mr_burst",
            checkout_request_id="cr_burst",
            status=MpesaPayment.Status.COMPLETED,
        )

        first = apply_campaign_addon_purchase(payment)
        second = apply_campaign_addon_purchase(payment)
        profile.refresh_from_db()

        assert first.pk == second.pk
        assert profile.seed_monthly_bonus == 10  # 5 existing burst + 5 new burst
        assert profile.burst_campaign_bonus == 10
        assert CampaignAddonPurchase.objects.filter(mpesa_payment=payment).count() == 1


@pytest.mark.django_db
class TestAddonCheckoutView:
    def test_addon_checkout_requires_login(self, client):
        url = reverse("billing:mpesa_addon_checkout")
        resp = client.post(url, {"addon_pack": "boost", "phone_number": "0712345678"})
        assert resp.status_code == 302
        assert "/login" in resp.url

    def test_addon_checkout_rejects_without_subscription(self, client, user):
        profile = user.profile
        profile.subscription_status = "none"
        profile.mpesa_phone = "254712345678"
        profile.save(update_fields=["subscription_status", "mpesa_phone"])
        user.phone_number = "0712345678"
        user.onboarding_completed = True
        user.save(update_fields=["phone_number", "onboarding_completed"])

        client.force_login(user)
        url = reverse("billing:mpesa_addon_checkout")
        resp = client.post(url, {"addon_pack": "boost", "phone_number": "0712345678"})
        assert resp.status_code == 302
        assert "pricing" in resp.url
