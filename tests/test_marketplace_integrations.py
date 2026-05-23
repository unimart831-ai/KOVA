"""Tests for marketplace integrations — CTA, sync images, webhooks."""

from unittest.mock import patch

import pytest

from apps.partners.models import MarketplacePartner, Partner
from apps.products.marketplace_sync import apply_sync_images_to_product_data, merge_sync_images
from apps.products.models import Product
from apps.products.product_cta import resolve_product_cta_url, uses_marketplace_cta


@pytest.mark.django_db
class TestProductCta:
    def test_marketplace_cta_uses_external_url(self, user):
        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-AAAA")
        mp = MarketplacePartner.objects.create(
            name="Jumia Test",
            slug="jumia-test",
            partner=partner,
            api_key_hash="abc123",
            api_key_prefix="kmp_test",
            enforce_marketplace_cta=True,
        )
        product = Product.objects.create(
            user=user,
            name="Phone",
            product_url="https://jumia.co.ke/phone-123",
            marketplace_partner=mp,
            source=Product.Source.MARKETPLACE,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        assert uses_marketplace_cta(product) is True
        assert resolve_product_cta_url(product) == "https://jumia.co.ke/phone-123"

    def test_direct_seller_uses_commerce_link(self, user, client):
        user.profile.page_slug = "my-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Lotion",
            price=500,
            commerce_slug="lotion",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        request = client.get("/").wsgi_request
        url = resolve_product_cta_url(product, request)
        assert "/shop/my-shop/lotion/" in url


class TestMarketplaceSyncHelpers:
    def test_merge_sync_images(self):
        images = merge_sync_images({
            "image_url": "https://cdn.example.com/main.jpg",
            "additional_images": ["https://cdn.example.com/extra.jpg", "https://cdn.example.com/main.jpg"],
        })
        assert images == [
            "https://cdn.example.com/main.jpg",
            "https://cdn.example.com/extra.jpg",
        ]

    def test_apply_sync_images_to_product_data(self):
        data = apply_sync_images_to_product_data({}, {"image_url": "https://cdn.example.com/a.jpg"})
        assert data["additional_images"] == ["https://cdn.example.com/a.jpg"]


@pytest.mark.django_db
class TestMarketplaceWebhooks:
    @patch("apps.partners.webhooks.dispatch_marketplace_webhook.delay")
    def test_notify_product_synced(self, mock_delay, user):
        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-BBBB")
        mp = MarketplacePartner.objects.create(
            name="Unimart",
            slug="unimart-test",
            partner=partner,
            api_key_hash="def456",
            api_key_prefix="kmp_uni",
            webhook_url="https://example.com/hook",
        )
        from apps.partners.models import MarketplaceSellerAccount
        from apps.partners.webhooks import notify_product_synced

        seller = MarketplaceSellerAccount.objects.create(
            marketplace=mp,
            user=user,
            external_seller_id="seller-1",
            status=MarketplaceSellerAccount.Status.ACTIVE,
        )
        notify_product_synced(mp, seller, created=2, updated=1, product_ids=["a", "b"])
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][1] == "product.synced"
