"""Tests for commerce SEO, shop index, sitemap, and robots."""

import pytest
from django.urls import reverse

from apps.products.commerce_links import resolve_public_shop, shop_index_path
from apps.products.commerce_seo import (
    build_breadcrumb_schema,
    build_seo_description,
    build_seo_title,
    commerce_seo_checklist,
    ensure_commerce_seo_copy,
    html_lang,
    build_local_business_schema,
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

    def test_html_lang_swahili(self, user):
        user.profile.content_language = "sw"
        assert html_lang(user.profile) == "sw"

        user.profile.content_language = "sw_en"
        assert html_lang(user.profile) == "sw"

    def test_breadcrumb_schema(self, rf):
        request = rf.get("/shop/demo/item/")
        schema = build_breadcrumb_schema(
            [
                {"label": "Demo Shop", "url": "/shop/demo/"},
                {"label": "Widget", "url": ""},
            ],
            request=request,
        )
        assert schema["@type"] == "BreadcrumbList"
        assert len(schema["itemListElement"]) == 2

    def test_local_business_schema_requires_city_and_whatsapp(self, user):
        user.profile.company_name = "Demo Shop"
        user.profile.city = "Nairobi"
        user.profile.cta_whatsapp = "254712345678"
        schema = build_local_business_schema(
            user.profile, user, "https://example.com/shop/demo/",
        )
        assert schema is not None
        assert schema["@type"] == "LocalBusiness"
        assert schema["address"]["addressLocality"] == "Nairobi"

        user.profile.cta_whatsapp = ""
        assert build_local_business_schema(user.profile, user, "https://example.com/shop/demo/") is None


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
        assert b"Shop our collection" in response.content or b"shop-section-title" in response.content
        assert b"Powered by" in response.content

    def test_public_shop_index_swahili_lang(self, client, user):
        user.profile.page_slug = "sw-shop"
        user.profile.content_language = "sw"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Bidhaa",
            commerce_slug="bidhaa",
            price=100,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        response = client.get(reverse("public_shop", kwargs={"page_slug": "sw-shop"}))
        assert b'lang="sw"' in response.content

    def test_public_shop_local_business_schema(self, client, user):
        user.profile.page_slug = "local-shop"
        user.profile.city = "Nairobi"
        user.profile.cta_whatsapp = "254712345678"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Local Item",
            commerce_slug="local-item",
            price=500,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        response = client.get(reverse("public_shop", kwargs={"page_slug": "local-shop"}))
        assert b'"@type": "LocalBusiness"' in response.content

    def test_public_shop_index_uses_profile_branding(self, client, user):
        user.profile.page_slug = "branded-shop"
        user.profile.company_name = "Branded Co"
        user.profile.brand_logo_url = "https://cdn.example.com/logo.png"
        user.profile.brand_colors = ["#7c3aed"]
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Branded Item",
            price=500,
            commerce_slug="branded-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        response = client.get(reverse("public_shop", kwargs={"page_slug": "branded-shop"}))
        content = response.content.decode()
        assert response.status_code == 200
        assert "https://cdn.example.com/logo.png" in content
        assert "#7c3aed" in content

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
        assert "All offers" in content

    def test_public_commerce_page_breadcrumb_schema(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Crumb Item",
            price=900,
            commerce_slug="crumb-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        url = reverse(
            "public_commerce",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        response = client.get(url)
        content = response.content.decode()
        assert '"@type": "BreadcrumbList"' in content
        assert 'property="product:price:amount"' in content

    def test_public_commerce_page_shows_related_products(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Shop"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Main Item",
            price=1000,
            commerce_slug="main-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        Product.objects.create(
            user=user,
            name="Related Item",
            price=800,
            commerce_slug="related-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        url = reverse(
            "public_commerce",
            kwargs={"page_slug": "demo-shop", "commerce_slug": "main-item"},
        )
        response = client.get(url)
        content = response.content.decode()
        assert response.status_code == 200
        assert "More from Demo Shop" in content
        assert "Related Item" in content

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
