"""Tests for platform-aware visual routing and Photoroom shadow defaults."""
from __future__ import annotations

import pytest

from apps.commerce.products.photoroom_plus import _default_shadow_mode
from apps.commerce.products.platform_visuals import (
    aspect_ratio_for,
    pick_platform_images,
    profile_for,
)


class TestPlatformVisuals:
    def test_instagram_carousel_prefers_portrait_feed(self):
        urls = [
            "/media/studio_polish/studio_white_abc.jpg",
            "/media/studio_polish/channel_feed_portrait_def.jpg",
            "/media/studio_polish/channel_story_ghi.jpg",
        ]
        picked = pick_platform_images(urls, platform="instagram", post_format="carousel")
        assert "channel_feed_portrait" in picked[0]

    def test_instagram_reel_prefers_story_export(self):
        urls = [
            "/media/studio_polish/studio_white_abc.jpg",
            "/media/studio_polish/channel_story_ghi.jpg",
        ]
        picked = pick_platform_images(urls, platform="instagram", post_format="reel")
        assert "channel_story" in picked[0]

    def test_reel_excludes_banner_and_carousel_jpegs(self):
        urls = [
            "/media/carousels/slide1.jpg",
            "/media/studio_polish/channel_banner_abc.jpg",
            "/media/studio_polish/channel_story_def.jpg",
        ]
        picked = pick_platform_images(urls, platform="tiktok", post_format="reel")
        assert len(picked) == 1
        assert "channel_story" in picked[0]

    def test_aspect_ratio_instagram_carousel_is_portrait(self):
        assert aspect_ratio_for("instagram", "carousel") == "portrait"

    def test_aspect_ratio_facebook_carousel_is_square(self):
        assert aspect_ratio_for("facebook", "carousel") == "square"

    def test_profile_exists_for_linkedin_reel(self):
        prof = profile_for("linkedin", "reel")
        assert prof is not None
        assert prof.aspect_ratio == "story"


class TestShadowDefaults:
    def test_uses_new_shadows_model_when_enabled(self, settings):
        settings.PHOTOROOM_AI_SHADOWS_MODEL_ENABLED = True
        assert _default_shadow_mode() == "ai.auto-with-overrides"

    def test_falls_back_to_legacy_shadow_when_disabled(self, settings):
        settings.PHOTOROOM_AI_SHADOWS_MODEL_ENABLED = False
        settings.PHOTOROOM_DEFAULT_SHADOW = "ai.preset-soft"
        assert _default_shadow_mode() == "ai.preset-soft"
