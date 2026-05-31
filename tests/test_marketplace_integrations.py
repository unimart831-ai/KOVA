"""Tests for marketplace integrations — CTA, sync images, webhooks."""

from unittest.mock import patch

import pytest

from apps.partners.marketplace_rules import is_platform_allowed, is_sandbox_publish
from apps.partners.models import MarketplacePartner, Partner, WebhookDeliveryLog
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

    @patch("apps.partners.webhooks.dispatch_marketplace_webhook.delay")
    def test_notify_seller_activated(self, mock_delay, user):
        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-CCCC")
        mp = MarketplacePartner.objects.create(
            name="Sandbox Mart",
            slug="sandbox-test",
            partner=partner,
            api_key_hash="ghi789",
            api_key_prefix="kmp_sbx",
            webhook_url="https://example.com/hook",
        )
        from apps.partners.models import MarketplaceSellerAccount
        from apps.partners.webhooks import notify_seller_activated

        seller = MarketplaceSellerAccount.objects.create(
            marketplace=mp,
            user=user,
            external_seller_id="seller-2",
            status=MarketplaceSellerAccount.Status.ACTIVE,
        )
        notify_seller_activated(mp, seller, auto_activated=True)
        mock_delay.assert_called_once()
        assert mock_delay.call_args[0][1] == "seller.activated"


@pytest.mark.django_db
class TestMarketplaceRules:
    def test_allowed_platforms_enforced(self, user):
        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-DDDD")
        mp = MarketplacePartner.objects.create(
            name="Restricted",
            slug="restricted-test",
            partner=partner,
            api_key_hash="jkl012",
            api_key_prefix="kmp_rst",
            settings={"allowed_platforms": ["instagram"]},
        )
        from apps.partners.models import MarketplaceSellerAccount

        MarketplaceSellerAccount.objects.create(
            marketplace=mp,
            user=user,
            external_seller_id="s1",
            status=MarketplaceSellerAccount.Status.ACTIVE,
        )
        assert is_platform_allowed(user, "instagram") is True
        assert is_platform_allowed(user, "facebook") is False

    def test_sandbox_flag(self, user):
        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-EEEE")
        mp = MarketplacePartner.objects.create(
            name="Sandbox",
            slug="sandbox-flag",
            partner=partner,
            api_key_hash="mno345",
            api_key_prefix="kmp_sb2",
            is_sandbox=True,
        )
        from apps.partners.models import MarketplaceSellerAccount

        MarketplaceSellerAccount.objects.create(
            marketplace=mp,
            user=user,
            external_seller_id="s2",
            status=MarketplaceSellerAccount.Status.ACTIVE,
        )
        assert is_sandbox_publish(user) is True


@pytest.mark.django_db
class TestWebhookDeliveryLog:
    def test_log_created_on_dispatch(self, user):
        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-FFFF")
        mp = MarketplacePartner.objects.create(
            name="Log Test",
            slug="log-test",
            partner=partner,
            api_key_hash="pqr678",
            api_key_prefix="kmp_log",
            webhook_url="https://example.com/hook",
        )
        from apps.partners.webhooks import _log_delivery

        _log_delivery(mp, "product.synced", {"created": 1}, status="success", response_code=200)
        assert WebhookDeliveryLog.objects.filter(marketplace=mp, event="product.synced").exists()


@pytest.mark.django_db
class TestSellerBulkProvision:
    def test_bulk_provision_sellers(self, user):
        from rest_framework.test import APIClient

        from apps.partners.models import hash_api_key

        partner = Partner.objects.create(user=user, referral_code="KOVA-TEST-GGGG")
        raw_key = "kmp_testbulkkey123456789012345678901234"
        mp = MarketplacePartner.objects.create(
            name="Bulk Test",
            slug="bulk-test",
            partner=partner,
            api_key_hash=hash_api_key(raw_key),
            api_key_prefix=raw_key[:8],
            seller_identity_field="external_id",
            auto_activate_sellers=True,
            seller_welcome_email=False,
        )

        api = APIClient()
        response = api.post(
            "/api/v1/partner/sellers/bulk/",
            {"sellers": [
                {"external_seller_id": "USK-100", "full_name": "A", "business_name": "Shop A"},
                {"external_seller_id": "USK-101", "full_name": "B", "business_name": "Shop B"},
            ]},
            format="json",
            HTTP_X_KOVA_PARTNER_KEY=raw_key,
        )

        assert response.status_code == 201
        body = response.json()
        assert body["summary"]["provisioned"] == 2
        assert mp.seller_accounts.filter(external_seller_id__in=["USK-100", "USK-101"]).count() == 2
