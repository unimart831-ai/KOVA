"""P1-2 brand kit settings + P1-5 lite polish routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.accounts.forms import PhotoroomBrandKitForm
from apps.products.photoroom_brand_template import build_photoroom_brand_template
from apps.products.polish_mode import (
    POLISH_MODE_LITE,
    POLISH_MODE_STUDIO,
    resolve_polish_mode,
    store_product_polish_mode,
)
from apps.products.models import Product
from apps.products.photo_variations import expand_product_photos


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Test Product",
        price=1000,
        currency="KES",
        visual_mode=Product.VisualMode.PRO_SCENE,
    )


@pytest.mark.django_db
class TestBrandKitSettingsSave:
    def test_brand_kit_form_persists_template(self, user):
        form = PhotoroomBrandKitForm(
            {
                "brand_kit_enabled": True,
                "shadow_mode": "ai.hard",
                "padding": "0.10",
                "studio_bg_pref": "dark",
                "outline_color": "#AABBCC",
            },
            profile=user.profile,
        )
        assert form.is_valid(), form.errors
        form.save(user.profile)
        user.profile.refresh_from_db()

        overrides = user.profile.photoroom_brand_template
        assert overrides["enabled"] is True
        assert overrides["shadow_mode"] == "ai.hard"
        assert overrides["padding"] == "0.10"
        assert overrides["studio_bg_pref"] == "dark"
        assert overrides["outline_color"] == "AABBCC"

        template = build_photoroom_brand_template(user.profile, user.pk)
        assert template.shadow_mode == "ai.hard"
        assert template.studio_color_hex == "1A1A2E"

    def test_settings_page_renders_brand_kit_section(self, auth_client):
        resp = auth_client.get(reverse("accounts:settings"))
        assert resp.status_code == 200
        assert b"settings-brand-kit" in resp.content
        assert b"Snap brand kit" in resp.content
        assert b"shadow_mode" in resp.content


@pytest.mark.django_db
class TestLitePolishRouting:
    @override_settings(PHOTOROOM_API_KEY="")
    def test_resolve_lite_when_photoroom_missing(self, user):
        assert resolve_polish_mode(user, POLISH_MODE_STUDIO) == POLISH_MODE_LITE

    @patch("apps.products.polish_mode.studio_polish_unavailable", return_value=True)
    def test_resolve_lite_when_platform_throttled(self, _mock, user):
        assert resolve_polish_mode(user, POLISH_MODE_STUDIO) == POLISH_MODE_LITE

    def test_explicit_lite_honored_when_studio_available(self, user):
        with patch("apps.products.polish_mode.studio_polish_unavailable", return_value=False):
            assert resolve_polish_mode(user, POLISH_MODE_LITE) == POLISH_MODE_LITE

    @patch("apps.products.photo_variations._expand_lite_polish")
    def test_expand_routes_to_lite(self, mock_lite, user, product):
        mock_lite.return_value = {"variations_created": 2, "mode": "lite"}
        store_product_polish_mode(product, POLISH_MODE_LITE)
        product.save(update_fields=["marketplace_metadata"])

        result = expand_product_photos(product, polish_mode=POLISH_MODE_LITE)

        mock_lite.assert_called_once()
        assert result["mode"] == "lite"

    @patch("apps.products.photo_variations._expand_studio_polish")
    @patch("apps.products.polish_mode.studio_polish_unavailable", return_value=False)
    def test_expand_routes_to_studio(self, _mock, mock_studio, user, product):
        mock_studio.return_value = {"variations_created": 3, "mode": "pro_scene"}
        result = expand_product_photos(product, polish_mode=POLISH_MODE_STUDIO)
        mock_studio.assert_called_once()
        assert result["mode"] == "pro_scene"


@pytest.mark.django_db
class TestSnapLaunchPolishMode:
    @patch("apps.utils.fire_task")
    @patch("apps.products.views.normalize_uploaded_image")
    def test_snap_launch_stores_lite_mode(self, mock_norm, mock_fire, auth_client, user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_norm.side_effect = lambda f: f
        img = SimpleUploadedFile("snap.jpg", b"fake-image-bytes", content_type="image/jpeg")
        url = reverse("products:snap_launch")
        with patch("apps.content.safety.check_uploaded_images_safe") as mock_safe:
            mock_safe.return_value = MagicMock(safe=True)
            resp = auth_client.post(
                url,
                {
                    "name": "Test Bag",
                    "price": "1500",
                    "currency": "KES",
                    "visual_mode": "pro_scene",
                    "polish_mode": "lite",
                    "scene_pack": "auto",
                    "photos": img,
                },
            )
        assert resp.status_code == 302
        created = Product.objects.filter(user=user).order_by("-created_at").first()
        assert created is not None
        assert created.marketplace_metadata.get("polish_mode") == "lite"
