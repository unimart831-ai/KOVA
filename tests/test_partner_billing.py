"""Tests for Growth Partners billing integration."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.billing.models import get_plan_limits
from apps.partners.models import Commission, Partner, Referral
from apps.partners.referral_billing import record_referral_payment_safe
from apps.partners.tasks import calculate_monthly_commissions, check_partner_milestones


@pytest.fixture
def growth_partner(db, user):
    partner_user = user
    return Partner.objects.create(user=partner_user, referral_code="KOVA-TEST-GROWTH")


@pytest.fixture
def referred_user(db):
    from apps.accounts.models import User, UserProfile

    u = User.objects.create_user(
        username="referred",
        email="referred@example.com",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="growth")
    u.refresh_from_db()
    return u


@pytest.fixture
def referral(growth_partner, referred_user):
    return Referral.objects.create(
        partner=growth_partner,
        referred_user=referred_user,
        referral_code_used=growth_partner.referral_code,
    )


@pytest.mark.django_db
class TestReferralBilling:
    def test_first_payment_increments_months(self, referral, referred_user):
        assert record_referral_payment_safe(referred_user, "growth") is True
        referral.refresh_from_db()
        assert referral.consecutive_paid_months == 1
        assert referral.activated_at is None
        assert referral.current_plan == "growth"

    def test_second_payment_activates_referral(self, referral, referred_user):
        record_referral_payment_safe(referred_user, "growth")
        record_referral_payment_safe(referred_user, "growth")
        referral.refresh_from_db()
        assert referral.consecutive_paid_months == 2
        assert referral.activated_at is not None
        assert referral.commission_expires_at is not None

    def test_duplicate_payment_same_month_skipped(self, referral, referred_user):
        record_referral_payment_safe(referred_user, "growth")
        assert record_referral_payment_safe(referred_user, "growth") is False
        referral.refresh_from_db()
        assert referral.consecutive_paid_months == 1

    def test_recalculate_tier_after_activation(self, referral, referred_user, growth_partner):
        record_referral_payment_safe(referred_user, "growth")
        record_referral_payment_safe(referred_user, "growth")
        growth_partner.refresh_from_db()
        assert growth_partner.commission_rate == Decimal("0.15")


@pytest.mark.django_db
class TestPartnerTasks:
    def test_monthly_commissions_created(self, referral, referred_user, growth_partner):
        record_referral_payment_safe(referred_user, "growth")
        record_referral_payment_safe(referred_user, "growth")

        result = calculate_monthly_commissions()
        assert result["commissions_created"] >= 1

        commission = Commission.objects.get(partner=growth_partner, referral=referral)
        revenue = Decimal(str(get_plan_limits("growth")["price_kes"]))
        expected = (revenue * growth_partner.commission_rate).quantize(Decimal("0.01"))
        assert commission.amount_kes == expected

        growth_partner.refresh_from_db()
        assert growth_partner.pending_payout_kes >= expected

    @patch("apps.emails.tasks.send_partner_milestone_email.delay")
    def test_milestone_awarded_at_threshold(self, mock_email, growth_partner, referred_user):
        for i in range(10):
            u = referred_user if i == 0 else None
            if i > 0:
                from apps.accounts.models import User, UserProfile

                u = User.objects.create_user(
                    username=f"ref{i}",
                    email=f"ref{i}@example.com",
                    password="TestPass123!",
                )
                UserProfile.objects.filter(user=u).update(plan="growth")
            Referral.objects.create(
                partner=growth_partner,
                referred_user=u,
                referral_code_used=growth_partner.referral_code,
                activated_at=timezone.now(),
            )

        result = check_partner_milestones()
        assert result["awards_created"] >= 1
        mock_email.assert_called()
