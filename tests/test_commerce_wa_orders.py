"""Tests for WhatsApp order click tracking and seller notifications."""

import pytest
from django.urls import reverse

from apps.insight.analytics.models import Conversion
from apps.create.content.campaigns import ensure_campaign_for_seed
from apps.create.content.models import ContentSeed
from apps.messaging.notifications.models import Notification
from apps.commerce.products.commerce_wa_orders import (
    build_tracked_whatsapp_order_url,
    build_wa_order_token,
    notify_seller_whatsapp_order_intent,
    parse_wa_order_token,
    resolve_whatsapp_order_redirect,
)
from apps.commerce.products.models import Product


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Leather Bag",
        price=4500,
        currency="KES",
        is_active=True,
        commerce_slug="leather-bag",
    )


@pytest.mark.django_db
class TestWaOrderToken:
    def test_roundtrip(self, user, product):
        token = build_wa_order_token(product_id=str(product.pk), source="product")
        data = parse_wa_order_token(token)
        assert data["product_id"] == str(product.pk)
        assert data["source"] == "product"


@pytest.mark.django_db
class TestTrackedWaUrl:
    def test_builds_signed_redirect(self, user, product):
        user.profile.cta_whatsapp = "254712345678"
        user.profile.save(update_fields=["cta_whatsapp"])
        url = build_tracked_whatsapp_order_url(
            user, user.profile, "Test Brand", product=product, source="product",
        )
        assert "/commerce/wa-order/" in url
        assert "t=" in url


@pytest.mark.django_db
class TestWaOrderRedirect:
    def test_redirect_tracks_and_notifies(self, client, user, product):
        user.profile.cta_whatsapp = "254712345678"
        user.profile.save(update_fields=["cta_whatsapp"])

        token = build_wa_order_token(product_id=str(product.pk), source="product")
        url = reverse("public_whatsapp_order") + f"?t={token}"
        resp = client.get(url)
        assert resp.status_code == 302
        assert resp.url.startswith("https://wa.me/")

        assert Conversion.objects.filter(
            user=user, event_name="whatsapp_order_click",
        ).exists()
        assert Notification.objects.filter(user=user).exists()

    def test_notify_seller_message(self, user, product):
        notify_seller_whatsapp_order_intent(
            user, product=product, campaign=None, source="product",
        )
        note = Notification.objects.filter(user=user).first()
        assert note is not None
        assert "Leather Bag" in note.message
