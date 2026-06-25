"""Kova plan limit and metering tests."""

import pytest
from django.utils import timezone

from apps.billing.models import (
    PLAN_LIMITS,
    TRIAL_CAMPAIGN_LIMIT,
    TRIAL_FEATURE_PLAN,
    get_effective_plan_tier,
    get_user_plan_limits,
)
from apps.billing.whatsapp_marketing import (
    check_whatsapp_marketing_limit,
    is_marketing_template,
)
from apps.agents.budget import check_budget
from apps.billing.exceptions import PlanLimitExceeded


@pytest.mark.django_db
class TestKovaPlanLimits:
    def test_kova_public_price(self):
        assert PLAN_LIMITS["kova"]["price_kes"] == 1300
        assert PLAN_LIMITS["kova"]["price_usd"] == 10
        assert PLAN_LIMITS["kova"]["max_seeds_per_month"] == 30

    def test_legacy_tiers_remain_for_grandfathered(self):
        assert PLAN_LIMITS["starter"]["price_kes"] == 499
        assert PLAN_LIMITS["growth"]["price_kes"] == 1499
        assert PLAN_LIMITS["pro"]["price_kes"] == 2999
        assert PLAN_LIMITS["agency"]["price_kes"] == 7999

    def test_no_unlimited_agency_posts(self):
        assert PLAN_LIMITS["agency"]["max_posts_per_month"] < 999999
        assert PLAN_LIMITS["agency"]["max_seeds_per_month"] == 120

    def test_monthly_llm_tokens_defined(self):
        for tier in ("kova", "starter", "growth", "pro", "agency"):
            assert PLAN_LIMITS[tier]["monthly_llm_tokens"] > 0

    def test_whatsapp_marketing_caps(self):
        assert PLAN_LIMITS["starter"]["whatsapp_marketing_conversations_per_month"] == 0
        assert PLAN_LIMITS["kova"]["whatsapp_marketing_conversations_per_month"] == 50
        assert PLAN_LIMITS["growth"]["whatsapp_marketing_conversations_per_month"] == 50
        assert PLAN_LIMITS["pro"]["whatsapp_marketing_conversations_per_month"] == 300

    def test_trial_uses_kova_limits_with_campaign_cap(self, user):
        profile = user.profile
        profile.plan = "kova"
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() + timezone.timedelta(days=3)
        profile.save(update_fields=["plan", "subscription_status", "trial_ends_at"])

        assert get_effective_plan_tier(profile) == TRIAL_FEATURE_PLAN
        limits = get_user_plan_limits(user)
        assert limits["max_seeds_per_month"] == TRIAL_CAMPAIGN_LIMIT
        assert limits["label"] == "Kova trial"
        assert limits["mpesa_commerce"] is True

    def test_kova_studio_polish_quota(self):
        assert PLAN_LIMITS["kova"]["visual_enhancements_per_month"] == 150


@pytest.mark.django_db
class TestWhatsAppMarketingEnforcement:
    def test_utility_template_skips_cap(self, user):
        class Template:
            category = "utility"

        assert is_marketing_template(Template()) is False
        allowed, _ = check_whatsapp_marketing_limit(user, template=Template())
        assert allowed is True

    def test_starter_blocks_marketing(self, user):
        user.profile.plan = "starter"
        user.profile.subscription_status = "active"
        user.profile.save(update_fields=["plan", "subscription_status"])

        class Template:
            category = "marketing"

        allowed, msg = check_whatsapp_marketing_limit(user, template=Template())
        assert allowed is False
        assert "not included" in msg.lower()

    def test_kova_allows_marketing(self, user):
        user.profile.plan = "kova"
        user.profile.subscription_status = "active"
        user.profile.save(update_fields=["plan", "subscription_status"])

        class Template:
            category = "marketing"

        allowed, _ = check_whatsapp_marketing_limit(user, template=Template())
        assert allowed is True


@pytest.mark.django_db
class TestMonthlyLlmBudget:
    def test_monthly_cap_raises(self, user):
        from datetime import timedelta
        from apps.agents.models import UserTokenBucket

        user.profile.plan = "starter"
        user.profile.subscription_status = "active"
        user.profile.save(update_fields=["plan", "subscription_status"])

        daily_cap = PLAN_LIMITS["starter"]["daily_llm_tokens"]
        monthly_cap = PLAN_LIMITS["starter"]["monthly_llm_tokens"]
        month_start = timezone.now().replace(day=1).date()
        days_needed = monthly_cap // daily_cap
        for i in range(days_needed):
            UserTokenBucket.objects.create(
                user=user,
                period_date=month_start + timedelta(days=i),
                input_tokens=daily_cap,
                output_tokens=0,
            )

        with pytest.raises(PlanLimitExceeded) as exc:
            check_budget(user, 1)
        assert exc.value.limit_type == "monthly_llm_tokens"
