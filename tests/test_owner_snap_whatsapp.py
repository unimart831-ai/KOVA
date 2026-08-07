"""Tests for WhatsApp owner Snap-to-Sell intake."""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.core.accounts.models import User, UserProfile
from apps.commerce.products.business_assets import sync_asset_from_product
from apps.commerce.products.models import BusinessAsset, Product
from apps.commerce.products.owner_snap_whatsapp import (
    launch_owner_snap,
    parse_snap_caption,
    try_complete_pending_snap,
)


@pytest.fixture
def snap_user(db):
    user = User.objects.create_user(
        username="seller",
        email="seller@kova.ai",
        password="x",
        phone_number="0711223344",
    )
    UserProfile.objects.filter(user=user).update(plan="growth")
    return user


def _tiny_jpeg() -> bytes:
    img = Image.new("RGB", (8, 8), color=(120, 80, 200))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestParseSnapCaption:
    def test_name_and_price(self):
        name, price = parse_snap_caption("Blue dress 2500")
        assert name == "Blue dress"
        assert price == Decimal("2500")

    def test_kes_prefix(self):
        name, price = parse_snap_caption("Samsung A54 KES 45,000")
        assert name == "Samsung A54"
        assert price == Decimal("45000")

    def test_name_only(self):
        name, price = parse_snap_caption("Leather bag")
        assert name == "Leather bag"
        assert price is None


class TestOwnerSnapFlow:
    def setup_method(self):
        cache.clear()

    @patch("apps.commerce.products.owner_snap_whatsapp.fire_task")
    @patch("apps.create.content.safety.check_uploaded_images_safe")
    @patch("apps.commerce.products.owner_snap_whatsapp._download_owner_media")
    def test_launch_with_caption_creates_product_and_asset(
        self,
        mock_download,
        mock_safety,
        mock_fire,
        snap_user,
    ):
        mock_download.return_value = (_tiny_jpeg(), "image/jpeg")
        mock_safety.return_value = type("R", (), {"safe": True})()

        text, key, ok, meta = launch_owner_snap(
            snap_user,
            media_id="media123",
            caption="Red shoes 1800",
        )

        assert ok is True
        assert key == "snap_launched"
        assert "Red shoes" in text
        product = Product.objects.get(pk=meta["product_id"])
        assert product.name == "Red shoes"
        assert product.price == Decimal("1800")
        assert product.source == Product.Source.SNAP
        asset = BusinessAsset.objects.get(pk=meta["asset_id"])
        assert asset.source == BusinessAsset.Source.WHATSAPP
        assert asset.product_id == product.pk
        mock_fire.assert_called_once()

    def test_image_without_details_sets_pending(self, snap_user):
        text, key, ok, _ = launch_owner_snap(
            snap_user,
            media_id="media456",
            caption="",
        )
        assert ok is True
        assert key == "snap_awaiting_details"
        assert cache.get(f"wa_owner_snap:{snap_user.pk}") is not None

    @patch("apps.commerce.products.owner_snap_whatsapp.fire_task")
    @patch("apps.create.content.safety.check_uploaded_images_safe")
    @patch("apps.commerce.products.owner_snap_whatsapp._download_owner_media")
    def test_complete_pending_with_price_only(
        self,
        mock_download,
        mock_safety,
        mock_fire,
        snap_user,
    ):
        mock_download.return_value = (_tiny_jpeg(), "image/jpeg")
        mock_safety.return_value = type("R", (), {"safe": True})()

        cache.set(
            f"wa_owner_snap:{snap_user.pk}",
            {"media_id": "media789", "mime_type": "image/jpeg", "caption": "Watch"},
            3600,
        )

        result = try_complete_pending_snap(snap_user, "3200")
        assert result is not None
        text, key, ok, meta = result
        assert ok is True
        assert key == "snap_launched"
        product = Product.objects.get(pk=meta["product_id"])
        assert product.name == "Watch"
        assert product.price == Decimal("3200")


class TestBusinessAssetSync:
    def test_sync_from_product(self, snap_user):
        product = Product.objects.create(
            user=snap_user,
            name="Test item",
            price=Decimal("500"),
            source=Product.Source.SNAP,
        )
        asset = sync_asset_from_product(product, source=BusinessAsset.Source.SNAP)
        assert asset.title == "Test item"
        assert asset.asset_type == BusinessAsset.AssetType.PRODUCT
        assert asset.metadata["price"] == "500"
