"""Tests for catalog product sampling into content."""

import pytest
from django.utils import timezone

from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount
from apps.commerce.products.models import Product
from apps.commerce.products.utils import (
    enrich_idea_with_product,
    resolve_product_by_name,
    sample_products_for_content,
    user_should_receive_catalog_sample,
)


@pytest.fixture
def ig(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        platform_user_id="ig1",
        username="shop",
        is_active=True,
    )


@pytest.mark.django_db
class TestCatalogSampling:
    def test_sample_prefers_never_promoted(self, user, ig):
        p1 = Product.objects.create(
            user=user, name="Widget A", stock_status=Product.StockStatus.IN_STOCK,
        )
        p2 = Product.objects.create(
            user=user, name="Widget B", stock_status=Product.StockStatus.IN_STOCK,
        )
        Post.objects.create(
            user=user,
            platform="instagram",
            social_account=ig,
            product=p1,
            content_text="Old post about Widget A",
            status="published",
        )
        sampled = sample_products_for_content(user, count=1)
        assert len(sampled) == 1
        assert sampled[0].pk == p2.pk

    def test_resolve_product_by_name(self, user):
        Product.objects.create(
            user=user, name="Blue Running Shoes", stock_status=Product.StockStatus.IN_STOCK,
        )
        assert resolve_product_by_name(user, "running shoes").name == "Blue Running Shoes"

    def test_enrich_idea_adds_product_name(self, user):
        p = Product.objects.create(
            user=user, name="Test Product", stock_status=Product.StockStatus.IN_STOCK,
        )
        idea = enrich_idea_with_product("Share a tip about quality.", p)
        assert "Test Product" in idea

    def test_sample_skips_recently_used(self, user, ig):
        p = Product.objects.create(
            user=user, name="Fresh Item", stock_status=Product.StockStatus.IN_STOCK,
        )
        ContentSeed.objects.create(user=user, product=p, idea="Recent seed")
        assert sample_products_for_content(user, count=1) == []

    def test_daily_sample_rate_is_deterministic(self, user):
        d = timezone.now().date()
        a = user_should_receive_catalog_sample(user, d)
        b = user_should_receive_catalog_sample(user, d)
        assert a == b
