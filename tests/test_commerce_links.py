"""Tests for public Commerce Links."""

import pytest
from django.urls import reverse

from apps.products.commerce_links import (
    commerce_link_path,
    ensure_commerce_slug,
    resolve_public_product,
)
from apps.products.models import Product


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
        user.profile.page_slug = "my-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Widget",
            price=100,
            commerce_slug="widget",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        path = commerce_link_path(product)
        assert path == "/shop/my-shop/widget/"

    def test_resolve_public_product(self, user):
        user.profile.page_slug = "kamau-shoes"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Sneakers",
            price=3000,
            commerce_slug="sneakers",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        profile, found = resolve_public_product("kamau-shoes", "sneakers")
        assert found.pk == product.pk
        assert profile.user_id == user.pk

    def test_public_commerce_page_renders(self, client, user):
        user.profile.page_slug = "demo-shop"
        user.profile.company_name = "Demo Shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Test Item",
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
        assert response.status_code == 200
        assert b"Test Item" in response.content
        assert b"Pay with M-Pesa" in response.content
