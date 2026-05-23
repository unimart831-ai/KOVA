"""
Tests for billing models, access helpers, and plan enforcement.
"""

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.billing.models import BillingEvent, MpesaPayment, PLAN_LIMITS


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
    def test_mpesa_payment_protect_on_delete(self, user):
        """MpesaPayment.user uses PROTECT — deleting user should fail."""
        from django.db.models import ProtectedError

        MpesaPayment.objects.create(
            user=user,
            phone_number="254712345678",
            amount=999,
            plan_tier="growth",
            merchant_request_id="mr_123",
            checkout_request_id="cr_123",
            status="pending",
        )
        with pytest.raises(ProtectedError):
            user.delete()


@pytest.mark.django_db
class TestPlanLimits:
    def test_plan_limits_exist(self):
        assert "starter" in PLAN_LIMITS
        assert "growth" in PLAN_LIMITS
        assert "pro" in PLAN_LIMITS
        assert "agency" in PLAN_LIMITS
        assert PLAN_LIMITS["starter"]["max_posts_per_month"] < PLAN_LIMITS["agency"]["max_posts_per_month"]

    def test_public_pricing_tiers(self):
        from apps.billing.models import PUBLIC_PLAN_TIERS, get_public_plan_limits

        assert PUBLIC_PLAN_TIERS == ("starter", "growth", "pro")
        public = get_public_plan_limits()
        assert set(public.keys()) == set(PUBLIC_PLAN_TIERS)
        assert "agency" not in public

    def test_starter_pricing_and_accounts(self):
        assert PLAN_LIMITS["starter"]["price_kes"] == 499
        assert PLAN_LIMITS["starter"]["max_social_accounts"] == 2
        assert PLAN_LIMITS["starter"]["trial_days"] == 7

    def test_growth_platform_ladder(self):
        assert PLAN_LIMITS["growth"]["max_social_accounts"] == 4
        assert PLAN_LIMITS["growth"]["price_kes"] == 999

    def test_pro_platform_ladder(self):
        assert PLAN_LIMITS["pro"]["max_social_accounts"] == 5
        assert PLAN_LIMITS["pro"]["whatsapp_enabled"] is True
        assert PLAN_LIMITS["pro"]["price_kes"] == 1999

    def test_user_profile_default_plan(self, user):
        profile = user.profile
        assert profile.plan in ("starter", "growth", "pro", "agency")


@pytest.mark.django_db
class TestBillingAccess:
    def test_can_start_free_trial_before_payment(self, user):
        from apps.billing.access import can_start_free_trial

        assert can_start_free_trial(user) is True

    def test_cannot_start_trial_after_mpesa_payment(self, user):
        from apps.billing.access import can_start_free_trial

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
        from apps.billing.access import subscription_allows_app_access

        profile = user.profile
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() - timezone.timedelta(days=1)
        profile.save(update_fields=["subscription_status", "trial_ends_at"])

        allowed, msg = subscription_allows_app_access(user)
        assert allowed is False
        assert "trial" in msg.lower()

    def test_active_trial_unlocks_kazi_features(self, user):
        from apps.billing.enforcement import check_mpesa_commerce, check_seed_limit
        from apps.billing.models import get_effective_plan_tier, get_user_plan_limits
        from apps.content.models import ContentSeed

        profile = user.profile
        profile.plan = "starter"
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() + timezone.timedelta(days=5)
        profile.save(update_fields=["plan", "subscription_status", "trial_ends_at"])

        assert get_effective_plan_tier(profile) == "growth"
        assert get_user_plan_limits(user)["mpesa_commerce"] is True

        allowed, _ = check_mpesa_commerce(user)
        assert allowed is True

        for i in range(5):
            ContentSeed.objects.create(user=user, idea=f"seed {i}")
        allowed, _ = check_seed_limit(user)
        assert allowed is True


@pytest.mark.django_db
class TestEnforcement:
    def test_seed_limit_blocks_at_cap(self, user):
        from apps.billing.enforcement import check_seed_limit
        from apps.content.models import ContentSeed

        profile = user.profile
        profile.plan = "starter"
        profile.subscription_status = "active"
        profile.save(update_fields=["plan", "subscription_status"])

        for i in range(5):
            ContentSeed.objects.create(user=user, idea=f"seed {i}")

        allowed, msg = check_seed_limit(user)
        assert allowed is False
        assert "seed" in msg.lower()

    def test_ab_testing_blocked_on_starter(self, user):
        from apps.billing.enforcement import check_ab_testing

        user.profile.plan = "starter"
        user.profile.subscription_status = "active"
        user.profile.save(update_fields=["plan", "subscription_status"])
        allowed, msg = check_ab_testing(user)
        assert allowed is False

    def test_llm_config_overrides_daily_cap(self, user):
        from apps.agents.models import LLMConfig
        from apps.billing.enforcement import get_daily_llm_token_cap

        config = LLMConfig.load()
        config.pk = 1
        config.plan_rate_limits = {"starter": {"max_tokens_per_day": 12345}}
        config.save()

        assert get_daily_llm_token_cap("starter") == 12345
