"""Tests for public Commerce Links."""

import pytest
from django.urls import reverse

from apps.commerce.products.commerce_links import (
    commerce_link_path,
    ensure_commerce_slug,
    resolve_public_product,
)
from apps.commerce.products.product_cta import resolve_product_cta_url
from apps.commerce.products.models import Product


@pytest.mark.django_db
class TestCommerceLinks:
    def test_ensure_commerce_slug(self, user):
        product = Product.objects.create(
            user=user,
            name="Blue Running Shoes",
            price=5000,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        slug = ensure_commerce_slug(product)
        assert slug == "blue-running-shoes"
        product.refresh_from_db()
        assert product.commerce_slug == slug

    def test_commerce_link_path(self, user):
        product = Product.objects.create(
            user=user,
            name="Hat",
            price=1000,
            commerce_slug="hat",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        user.profile.page_slug = "my-shop"
        user.profile.save()
        path = commerce_link_path(product)
        assert path == "/shop/my-shop/hat/"

    def test_resolve_public_product(self, user):
        user.profile.page_slug = "demo-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Sneaker",
            price=3000,
            commerce_slug="sneaker",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        found = resolve_public_product("demo-shop", "sneaker")
        assert found == product

    def test_public_commerce_page(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Sneaker",
            price=3000,
            commerce_slug="sneaker",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        url = reverse(
            "public_commerce",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        response = client.get(url)
        assert response.status_code == 200
        assert b"Sneaker" in response.content

    def test_public_commerce_pay_requires_phone_not_500(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Pay Test",
            price=500,
            currency="KES",
            commerce_slug="pay-test",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        url = reverse(
            "public_commerce_pay",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        response = client.post(url)
        assert response.status_code == 400
        assert response.json()["error"] == "Phone number is required."

    def test_service_offer_uses_fulfillment_url_cta(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Studio"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Strategy Session",
            offering_type=Product.OfferingType.SERVICE,
            commerce_slug="strategy-session",
            fulfillment_url="https://example.com/book-strategy",
            stock_status=Product.StockStatus.UNLIMITED,
        )

        cta_url = resolve_product_cta_url(product)
        assert cta_url == "https://example.com/book-strategy"

        url = reverse(
            "public_commerce",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        response = client.get(url)
        assert response.status_code == 200
        assert b"Book this service" in response.content or b"Book now" in response.content
        assert b"Pay with M-Pesa" not in response.content

    def test_digital_offer_shows_access_flow(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Studio"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Creator Toolkit",
            offering_type=Product.OfferingType.DIGITAL,
            commerce_slug="creator-toolkit",
            fulfillment_url="https://example.com/toolkit",
            fulfillment_notes="Access is delivered instantly after signup.",
            stock_status=Product.StockStatus.UNLIMITED,
        )

        url = reverse(
            "public_commerce",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        response = client.get(url)
        assert response.status_code == 200
        assert b"Get this digital offer" in response.content
        assert b"Get instant access" in response.content
        assert b"Access is delivered instantly after signup." in response.content
        assert b"Pay with M-Pesa" not in response.content
