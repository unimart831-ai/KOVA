"""Tests for campaign-level revenue attribution."""

import pytest
from decimal import Decimal

from apps.insight.analytics.models import Conversion
from apps.create.content.campaign_attribution import (
    campaign_funnel_stats,
    campaign_revenue_brief_lines,
    create_attributed_conversion,
    resolve_marketing_campaign,
    top_campaigns_by_revenue,
)
from apps.create.content.campaigns import ensure_campaign_for_seed
from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount
from apps.commerce.products.models import Product


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Weekend Handbag",
        price=12400,
        currency="KES",
        is_active=True,
        commerce_slug="weekend-handbag",
    )


@pytest.fixture
def ig_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        platform_user_id="ig-1",
        username="testig",
        is_active=True,
    )


@pytest.mark.django_db
class TestResolveMarketingCampaign:
    def test_from_post_seed(self, user, product, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
        campaign = ensure_campaign_for_seed(seed, title="Weekend handbag sale")
        post = Post.objects.create(
            user=user,
            seed=seed,
            social_account=ig_account,
            platform="instagram",
            content_text="Sale post",
            utm_campaign=campaign.slug,
        )
        resolved = resolve_marketing_campaign(user, post=post)
        assert resolved.pk == campaign.pk

    def test_from_utm_slug(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Flash")
        campaign = ensure_campaign_for_seed(seed, title="Flash sale")
        resolved = resolve_marketing_campaign(user, utm_campaign=campaign.slug)
        assert resolved.pk == campaign.pk


@pytest.mark.django_db
class TestAttributedConversion:
    def test_sets_marketing_campaign_fk(self, user, product):
        seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
        campaign = ensure_campaign_for_seed(seed, title="Weekend handbag sale")

        conv = create_attributed_conversion(
            user,
            Conversion.ConversionType.SALE,
            product=product,
            campaign=campaign,
            revenue=Decimal("12400"),
            event_name="mpesa_TEST123",
        )
        assert conv.marketing_campaign_id == campaign.pk
        assert conv.metadata["campaign_id"] == str(campaign.pk)
        assert conv.utm_campaign == campaign.slug


@pytest.mark.django_db
class TestCampaignFunnel:
    def test_funnel_aggregation(self, user, product):
        seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
        campaign = ensure_campaign_for_seed(seed, title="Weekend handbag sale")

        create_attributed_conversion(
            user, Conversion.ConversionType.CLICK,
            campaign=campaign, event_name="campaign_page_view",
        )
        create_attributed_conversion(
            user, Conversion.ConversionType.LEAD,
            campaign=campaign, product=product, event_name="whatsapp_order_click",
        )
        create_attributed_conversion(
            user, Conversion.ConversionType.SALE,
            campaign=campaign, product=product,
            revenue=Decimal("12400"), event_name="mpesa_R1",
        )

        stats = campaign_funnel_stats(campaign, days=7)
        assert stats.sales == 1
        assert stats.leads == 1
        assert float(stats.revenue) == 12400.0

    def test_brief_line(self, user, product):
        seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
        campaign = ensure_campaign_for_seed(seed, title="Weekend handbag sale")
        create_attributed_conversion(
            user, Conversion.ConversionType.SALE,
            campaign=campaign, revenue=Decimal("12400"), event_name="mpesa_R2",
        )
        lines = campaign_revenue_brief_lines(user, days=7, limit=1)
        assert lines
        assert "12,400" in lines[0]
        assert "Weekend handbag" in lines[0]

    def test_top_campaigns_ranking(self, user, product):
        seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
        campaign = ensure_campaign_for_seed(seed, title="Winner campaign")
        create_attributed_conversion(
            user, Conversion.ConversionType.SALE,
            campaign=campaign, revenue=Decimal("5000"), event_name="mpesa_R3",
        )
        tops = top_campaigns_by_revenue(user, days=7, limit=3)
        assert len(tops) == 1
        assert tops[0]["revenue"] == 5000.0


@pytest.mark.django_db
class TestCampaignPerformanceDashboard:
    def test_performance_rows_and_objective_comparison(self, user, product, ig_account):
        from apps.create.content.campaign_attribution import (
            get_campaign_performance_rows,
            get_objective_platform_comparison,
        )

        seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
        campaign = ensure_campaign_for_seed(seed, title="IG winner")
        campaign.objective = "sales"
        campaign.save(update_fields=["objective"])
        post = Post.objects.create(
            user=user,
            seed=seed,
            social_account=ig_account,
            platform="instagram",
            content_text="Buy now",
        )
        create_attributed_conversion(
            user, Conversion.ConversionType.SALE,
            campaign=campaign, post=post, product=product,
            revenue=Decimal("8000"), event_name="mpesa_R4",
        )

        rows = get_campaign_performance_rows(user, days=7)
        assert len(rows) == 1
        assert rows[0]["revenue"] == 8000.0
        assert rows[0]["sales"] == 1
        assert rows[0]["platforms"][0]["platform"] == "instagram"

        comparison = get_objective_platform_comparison(user, days=7)
        assert comparison
        assert comparison[0]["objective"] == "sales"
        assert comparison[0]["platforms"][0]["revenue"] == 8000.0
