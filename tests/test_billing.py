"""
Tests for billing models, access helpers, and plan enforcement.
"""

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.core.accounts.models import User, UserProfile
from apps.core.billing.models import AgencySalesInquiry, BillingEvent, MpesaPayment, PLAN_LIMITS


@pytest.mark.django_db
class TestBillingEvent:
    def test_create_billing_event(self, user):
        event = BillingEvent.objects.create(
            user=user,
            event_type="subscription_created",
            provider="stripe",
            stripe_event_id="evt_test_123",
        )
        assert event.pk is not None
        assert event.provider == "stripe"

    def test_billing_event_str(self, user):
        event = BillingEvent.objects.create(
            user=user,
            event_type="payment_success",
            provider="mpesa",
            stripe_event_id="mpesa_cr_test",
        )
        assert "payment_success" in str(event)


@pytest.mark.django_db
class TestMpesaPayment:
    def test_mpesa_payment_protect_on_hard_delete(self, user):
        """MpesaPayment.user uses PROTECT — hard delete should fail."""
        from django.db import models
        from django.db.models import ProtectedError

        MpesaPayment.objects.create(
            user=user,
            phone_number="254712345678",
            amount=1300,
            plan_tier="kova",
            merchant_request_id="mr_123",
            checkout_request_id="cr_123",
            status="pending",
        )
        with pytest.raises(ProtectedError):
            models.Model.delete(user)


@pytest.mark.django_db
class TestPlanLimits:
    def test_plan_limits_exist(self):
        assert "kova" in PLAN_LIMITS
        assert "starter" in PLAN_LIMITS
        assert "growth" in PLAN_LIMITS
        assert "pro" in PLAN_LIMITS
        assert "agency" in PLAN_LIMITS
        assert PLAN_LIMITS["kova"]["max_seeds_per_month"] == 30
        assert PLAN_LIMITS["kova"]["price_kes"] == 1300

    def test_public_pricing_tiers(self):
        from apps.core.billing.models import PUBLIC_PLAN_TIERS, get_public_plan_limits

        assert PUBLIC_PLAN_TIERS == ("kova",)
        public = get_public_plan_limits()
        assert set(public.keys()) == {"kova"}
        assert "agency" not in public

    def test_kova_plan_quality_features(self):
        kova = PLAN_LIMITS["kova"]
        assert kova["bannerbear_carousels_enabled"] is True
        assert kova["mpesa_commerce"] is True
        assert kova["visual_enhancements_per_month"] >= 150

    def test_user_profile_default_plan(self, user):
        profile = user.profile
        assert profile.plan in ("kova", "starter", "growth", "pro", "agency")


@pytest.mark.django_db
class TestSidebarPlanDisplay:
    def test_active_trial_shows_starter_trial(self, user):
        from apps.core.billing.models import get_sidebar_plan_display

        profile = user.profile
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() + timezone.timedelta(days=5)
        profile.plan = "growth"
        profile.save(update_fields=["subscription_status", "trial_ends_at", "plan"])

        display = get_sidebar_plan_display(user)
        assert display["label"] == "Kova trial"
        assert display["variant"] == "trial"

    def test_active_paid_shows_tier_name(self, user):
        from apps.core.billing.models import get_sidebar_plan_display

        profile = user.profile
        profile.plan = "pro"
        profile.subscription_status = "active"
        profile.save(update_fields=["plan", "subscription_status"])

        display = get_sidebar_plan_display(user)
        assert display["label"] == "Pro"
        assert display["variant"] == "paid"

    def test_no_subscription_shows_free(self, user):
        from apps.core.billing.models import get_sidebar_plan_display

        profile = user.profile
        profile.subscription_status = "none"
        profile.save(update_fields=["subscription_status"])

        display = get_sidebar_plan_display(user)
        assert display["label"] == "Free"
        assert display["variant"] == "free"

    def test_agency_without_approval_shows_pending(self, user):
        from apps.core.billing.models import get_sidebar_plan_display

        profile = user.profile
        profile.plan = "agency"
        profile.subscription_status = "active"
        profile.is_agency_approved = False
        profile.save(update_fields=["plan", "subscription_status", "is_agency_approved"])

        display = get_sidebar_plan_display(user)
        assert display["label"] == "Agency pending"
        assert display["variant"] == "pending"

    def test_sidebar_label_in_app_layout(self, client, user):
        profile = user.profile
        profile.plan = "kova"
        profile.subscription_status = "active"
        profile.save(update_fields=["plan", "subscription_status"])
        user.phone_number = "0712345678"
        user.onboarding_completed = True
        user.save(update_fields=["phone_number", "onboarding_completed"])

        client.force_login(user)
        resp = client.get(reverse("brief:home"))
        assert resp.status_code == 200
        assert b"Kova" in resp.content


@pytest.mark.django_db
class TestBillingAccess:
    def test_can_start_free_trial_before_payment(self, user):
        from apps.core.billing.access import can_start_free_trial

        assert can_start_free_trial(user) is True

    def test_cannot_start_trial_after_mpesa_payment(self, user):
        from apps.core.billing.access import can_start_free_trial

        MpesaPayment.objects.create(
            user=user,
            phone_number="254712345678",
            amount=999,
            plan_tier="growth",
            merchant_request_id="mr_paid",
            checkout_request_id="cr_paid",
            status=MpesaPayment.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        assert can_start_free_trial(user) is False

    def test_expired_trial_blocks_access(self, user):
        from apps.core.billing.access import subscription_allows_app_access

        profile = user.profile
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() - timezone.timedelta(days=1)
        profile.save(update_fields=["subscription_status", "trial_ends_at"])

        allowed, msg = subscription_allows_app_access(user)
        assert allowed is False
        assert "trial" in msg.lower()

    def test_active_trial_uses_kova_features_with_campaign_cap(self, user):
        from apps.core.billing.enforcement import check_ab_testing, check_seed_limit
        from apps.core.billing.models import TRIAL_CAMPAIGN_LIMIT, get_effective_plan_tier, get_user_plan_limits
        from apps.create.content.campaigns import ensure_campaign_for_seed
        from apps.create.content.models import ContentSeed

        profile = user.profile
        profile.plan = "kova"
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() + timezone.timedelta(days=5)
        profile.save(update_fields=["plan", "subscription_status", "trial_ends_at"])

        assert get_effective_plan_tier(profile) == "kova"
        assert get_user_plan_limits(user)["mpesa_commerce"] is True
        assert get_user_plan_limits(user)["max_seeds_per_month"] == TRIAL_CAMPAIGN_LIMIT

        allowed, _ = check_ab_testing(user)
        assert allowed is True

        for i in range(TRIAL_CAMPAIGN_LIMIT):
            seed = ContentSeed.objects.create(user=user, idea=f"campaign {i}")
            ensure_campaign_for_seed(seed, title=f"campaign {i}")
        allowed, _ = check_seed_limit(user)
        assert allowed is False


@pytest.mark.django_db
class TestEnforcement:
    def test_seed_limit_blocks_at_cap(self, user):
        from apps.core.billing.enforcement import check_seed_limit
        from apps.create.content.campaigns import ensure_campaign_for_seed
        from apps.create.content.models import ContentSeed

        profile = user.profile
        profile.plan = "starter"
        profile.subscription_status = "active"
        profile.save(update_fields=["plan", "subscription_status"])

        for i in range(8):
            seed = ContentSeed.objects.create(user=user, idea=f"seed {i}")
            ensure_campaign_for_seed(seed, title=f"seed {i}")

        allowed, msg = check_seed_limit(user)
        assert allowed is False
        assert "marketing campaign" in msg.lower()

    def test_ab_testing_not_gated_in_v1(self, user):
        from apps.core.billing.enforcement import check_ab_testing

        user.profile.plan = "starter"
        user.profile.subscription_status = "active"
        user.profile.save(update_fields=["plan", "subscription_status"])
        allowed, msg = check_ab_testing(user)
        assert allowed is True
        assert msg == ""

    def test_llm_config_overrides_daily_cap(self, user):
        from apps.create.agents.models import LLMConfig
        from apps.core.billing.enforcement import get_daily_llm_token_cap

        config = LLMConfig.load()
        config.pk = 1
        config.plan_rate_limits = {"starter": {"max_tokens_per_day": 12345}}
        config.save()

        assert get_daily_llm_token_cap("starter") == 12345


@pytest.mark.django_db
class TestAgencySalesInquiry:
    def test_contact_sales_submit_anonymous(self, client):
        url = reverse("billing:contact_sales")
        resp = client.post(url, {
            "name": "Jane Agency",
            "email": "jane@agency.co.ke",
            "phone": "0712345678",
            "company_name": "Jane Digital",
            "message": "We manage 15 SMB clients.",
            "client_count": 15,
            "plan_interest": "agency",
        })
        assert resp.status_code == 200
        assert AgencySalesInquiry.objects.filter(email="jane@agency.co.ke").exists()
        assert b"Thank you" in resp.content

    def test_contact_sales_prefill_logged_in(self, client, user):
        user.full_name = "Alex Wakala"
        user.phone_number = "0712345678"
        user.onboarding_completed = True
        user.save(update_fields=["full_name", "phone_number", "onboarding_completed"])
        client.force_login(user)
        resp = client.get(reverse("billing:contact_sales"))
        assert resp.status_code == 200
        assert b"Alex Wakala" in resp.content
        assert user.email.encode() in resp.content

    def test_staff_list_requires_staff(self, client, user, staff_user):
        inquiry = AgencySalesInquiry.objects.create(
            name="Test",
            email="test@agency.com",
            message="Hello",
        )
        resp = client.get(reverse("admin_dashboard:sales_inquiry_list"))
        assert resp.status_code == 302

        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:sales_inquiry_list"))
        assert resp.status_code == 200
        assert inquiry.email.encode() in resp.content

    def test_notify_staff_on_submit(self, client, superuser, settings):
        settings.DEFAULT_FROM_EMAIL = "Kova <noreply@test.local>"
        client.post(reverse("billing:contact_sales"), {
            "name": "Notify Test",
            "email": "notify@test.local",
            "message": "Please call back.",
        })
        assert len(mail.outbox) >= 1
        assert "Agency sales" in mail.outbox[0].subject
