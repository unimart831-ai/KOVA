"""
Tests for billing models and plan enforcement.
"""

import pytest

from apps.accounts.models import User, UserProfile
from apps.billing.models import BillingEvent, MpesaPayment


@pytest.mark.django_db
class TestBillingEvent:
    def test_create_billing_event(self, user):
        event = BillingEvent.objects.create(
            user=user,
            event_type="subscription_created",
            provider="stripe",
            amount=2999,
            currency="KES",
        )
        assert event.pk is not None
        assert event.provider == "stripe"

    def test_billing_event_str(self, user):
        event = BillingEvent.objects.create(
            user=user,
            event_type="payment_success",
            provider="mpesa",
            amount=999,
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
