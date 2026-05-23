"""
Tests for billing models, access helpers, and plan enforcement.
"""

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.billing.models import BillingEvent, MpesaPayment


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
        from apps.billing.models import PLAN_LIMITS

        assert "starter" in PLAN_LIMITS
        assert "growth" in PLAN_LIMITS
        assert "pro" in PLAN_LIMITS
        assert "agency" in PLAN_LIMITS
        assert PLAN_LIMITS["starter"]["max_posts_per_month"] < PLAN_LIMITS["agency"]["max_posts_per_month"]

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


@pytest.mark.django_db
class TestEnforcement:
    def test_seed_limit_blocks_at_cap(self, user):
        from apps.billing.enforcement import check_seed_limit
        from apps.content.models import ContentSeed

        for i in range(5):
            ContentSeed.objects.create(user=user, idea=f"seed {i}")

        allowed, msg = check_seed_limit(user)
        assert allowed is False
        assert "seed" in msg.lower()

    def test_ab_testing_blocked_on_starter(self, user):
        from apps.billing.enforcement import check_ab_testing

        user.profile.plan = "starter"
        user.profile.save(update_fields=["plan"])
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
