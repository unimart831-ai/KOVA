"""Tests for commerce SEO, shop index, sitemap, and robots."""

import pytest
from django.urls import reverse

from apps.products.commerce_links import resolve_public_shop, shop_index_path
from apps.products.commerce_seo import (
    build_seo_description,
    build_seo_title,
    commerce_seo_checklist,
    ensure_commerce_seo_copy,
)
from apps.products.models import Product


@pytest.mark.django_db
class TestCommerceSeoHelpers:
    def test_build_seo_title_includes_price_and_brand(self, user):
        user.profile.company_name = "Kova Agents"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Amara Body Lotion",
            price=350,
            currency="KES",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        title = build_seo_title(product, user.profile, user)
        assert "Amara Body Lotion" in title
        assert "KES" in title
        assert "Kova Agents" in title

    def test_build_seo_description_from_product_copy(self, user):
        user.profile.company_name = "Demo Shop"
        user.profile.city = "Nairobi"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Widget",
            description="A premium widget for everyday use. Soft touch and long lasting.",
            price=500,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        desc = build_seo_description(
            product, user.profile, user, mpesa_available=True, whatsapp_available=True,
        )
        assert "premium widget" in desc

    def test_build_seo_description_generated_when_thin(self, user):
        user.profile.company_name = "Demo Shop"
        user.profile.city = "Nairobi"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Widget",
            price=500,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        desc = build_seo_description(
            product, user.profile, user, mpesa_available=True, whatsapp_available=False,
        )
        assert "Widget" in desc
        assert "Nairobi" in desc
        assert "M-Pesa" in desc

    def test_ensure_commerce_seo_copy_fills_thin_description(self, user):
        user.profile.company_name = "Demo Shop"
        user.profile.city = "Nairobi"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Toothpick Container",
            price=200,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        updated = ensure_commerce_seo_copy(product, user.profile)
        assert updated is True
        product.refresh_from_db()
        assert len(product.description) >= 40
        assert "Toothpick Container" in product.description

    def test_commerce_seo_checklist_scores_incomplete_product(self, user):
        product = Product.objects.create(
            user=user,
            name="New product",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        checklist = commerce_seo_checklist(product, user.profile)
        assert checklist["ready"] is False
        assert checklist["done_count"] < checklist["total"]


@pytest.mark.django_db
class TestPublicShopPages:
    def test_resolve_public_shop(self, user):
        user.profile.page_slug = "my-store"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Item A",
            commerce_slug="item-a",
            price=100,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        profile, products = resolve_public_shop("my-store")
        assert profile.user_id == user.pk
        assert len(products) == 1

    def test_shop_index_path(self, user):
        user.profile.page_slug = "my-store"
        user.profile.save()
        assert shop_index_path(user.profile) == "/shop/my-store/"

    def test_public_shop_index_renders(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Shop"
        user.profile.page_headline = "Quality goods in Nairobi"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Test Item",
            price=1500,
            currency="KES",
            commerce_slug="test-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        url = reverse("public_shop", kwargs={"page_slug": "demo-shop"})
        response = client.get(url)
        assert response.status_code == 200
        assert b"Demo Shop" in response.content
        assert b"Test Item" in response.content
        assert b'application/ld+json' in response.content
        assert b'"@type": "Store"' in response.content

    def test_public_commerce_page_has_seo_meta(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Test Item",
            description="A great test item for your home and office needs.",
            price=1500,
            currency="KES",
            commerce_slug="test-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        url = reverse(
            "public_commerce",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        response = client.get(url)
        content = response.content.decode()
        assert response.status_code == 200
        assert 'rel="canonical"' in content
        assert 'property="og:title"' in content
        assert '"@type": "Product"' in content
        assert "View all products" in content

    def test_sitemap_lists_shop_and_product(self, client, user):
        user.profile.page_slug = "seo-shop"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Sitemap Item",
            commerce_slug="sitemap-item",
            price=99,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        response = client.get(reverse("sitemap"))
        content = response.content.decode()
        assert response.status_code == 200
        assert "/shop/seo-shop/" in content
        assert "/shop/seo-shop/sitemap-item/" in content

    def test_robots_allows_shop(self, client):
        response = client.get(reverse("robots_txt"))
        content = response.content.decode()
        assert response.status_code == 200
        assert "Allow: /shop/" in content
        assert "Sitemap:" in content
