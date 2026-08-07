"""Tests for default campaign / commerce post CTAs."""

import pytest

from apps.create.content.campaign_cta import (
    apply_default_campaign_cta,
    campaign_cta_label,
    resolve_post_commerce_url,
)
from apps.create.content.campaigns import ensure_campaign_for_seed
from apps.create.content.models import ContentSeed, Post
from apps.commerce.products.models import Product


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Test Handbag",
        price=2500,
        currency="KES",
        is_active=True,
        commerce_slug="test-handbag",
    )


@pytest.mark.django_db
class TestResolvePostCommerceUrl:
    def test_campaign_page_wins_over_product(self, user, product):
        seed = ContentSeed.objects.create(
            user=user,
            idea="Weekend handbag sale",
            product=product,
            status=ContentSeed.SeedStatus.PROCESSING,
        )
        campaign = ensure_campaign_for_seed(seed, title="Weekend handbag sale")
        url = resolve_post_commerce_url(seed, user)
        assert f"/c/{campaign.slug}/" in url

    def test_product_shop_when_no_campaign(self, user, product):
        seed = ContentSeed.objects.create(
            user=user,
            idea="Simple product post",
            product=product,
        )
        url = resolve_post_commerce_url(seed, user)
        assert "/shop/" in url


@pytest.mark.django_db
class TestApplyDefaultCampaignCta:
    def test_sets_link_cta_on_post(self, user, product):
        seed = ContentSeed.objects.create(
            user=user,
            idea="Flash sale",
            product=product,
            status=ContentSeed.SeedStatus.PROCESSING,
        )
        ensure_campaign_for_seed(seed, title="Flash sale")
        post = Post.objects.create(
            user=user,
            seed=seed,
            product=product,
            platform="facebook",
            content_text="Great offer today",
        )
        assert apply_default_campaign_cta(post, user, seed) is True
        post.refresh_from_db()
        assert post.cta_type == "link"
        assert post.cta_url
        assert "/c/" in post.cta_url
        assert post.utm_campaign

    def test_skips_when_cta_already_set(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Test")
        post = Post.objects.create(
            user=user,
            seed=seed,
            platform="facebook",
            content_text="Hello",
            cta_type="link",
            cta_url="https://example.com",
        )
        assert apply_default_campaign_cta(post, user, seed) is False


@pytest.mark.django_db
def test_campaign_cta_label_for_sales(user, product):
    seed = ContentSeed.objects.create(user=user, idea="Sale", product=product)
    campaign = ensure_campaign_for_seed(seed, title="Summer bags", objective="sales")
    label = campaign_cta_label(seed, campaign)
    assert "Summer bags" in label
