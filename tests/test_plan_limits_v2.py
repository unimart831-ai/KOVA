"""Plan v2 limit and metering tests."""

import pytest
from django.utils import timezone

from apps.billing.models import PLAN_LIMITS, get_effective_plan_tier, get_user_plan_limits
from apps.billing.whatsapp_marketing import (
    check_whatsapp_marketing_limit,
    is_marketing_template,
)
from apps.agents.budget import check_budget
from apps.billing.exceptions import PlanLimitExceeded


@pytest.mark.django_db
class TestPlanV2Limits:
    def test_v2_prices(self):
        assert PLAN_LIMITS["starter"]["price_kes"] == 499
        assert PLAN_LIMITS["growth"]["price_kes"] == 1499
        assert PLAN_LIMITS["pro"]["price_kes"] == 2999
        assert PLAN_LIMITS["agency"]["price_kes"] == 7999

    def test_no_unlimited_agency_posts(self):
        assert PLAN_LIMITS["agency"]["max_posts_per_month"] < 999999
        assert PLAN_LIMITS["agency"]["max_seeds_per_month"] == 120

    def test_monthly_llm_tokens_defined(self):
        for tier in ("starter", "growth", "pro", "agency"):
            assert PLAN_LIMITS[tier]["monthly_llm_tokens"] > 0

    def test_whatsapp_marketing_caps(self):
        assert PLAN_LIMITS["starter"]["whatsapp_marketing_conversations_per_month"] == 0
        assert PLAN_LIMITS["growth"]["whatsapp_marketing_conversations_per_month"] == 50
        assert PLAN_LIMITS["pro"]["whatsapp_marketing_conversations_per_month"] == 300

    def test_trial_uses_starter_limits(self, user):
        profile = user.profile
        profile.plan = "growth"
        profile.subscription_status = "trialing"
        profile.trial_ends_at = timezone.now() + timezone.timedelta(days=3)
        profile.save(update_fields=["plan", "subscription_status", "trial_ends_at"])

        assert get_effective_plan_tier(profile) == "starter"
        limits = get_user_plan_limits(user)
        assert limits["max_seeds_per_month"] == PLAN_LIMITS["starter"]["max_seeds_per_month"]
        assert limits["label"] == "Starter trial"

    def test_studio_polish_starter_taste(self):
        assert PLAN_LIMITS["starter"]["visual_enhancements_per_month"] == 8


@pytest.mark.django_db
class TestWhatsAppMarketingEnforcement:
    def test_utility_template_skips_cap(self, user):
        class Template:
            category = "utility"

        assert is_marketing_template(Template()) is False
        allowed, _ = check_whatsapp_marketing_limit(user, template=Template())
        assert allowed is True

    def test_starter_blocks_marketing(self, user):
        class Template:
            category = "marketing"

        allowed, msg = check_whatsapp_marketing_limit(user, template=Template())
        assert allowed is False
        assert "not included" in msg.lower()


@pytest.mark.django_db
class TestMonthlyLlmBudget:
    def test_monthly_cap_raises(self, user):
        from datetime import timedelta
        from apps.agents.models import UserTokenBucket

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
