"""Tests for reel image curation."""

from apps.products.reel_curation import curate_reel_image_urls


def test_curate_orders_story_then_ai_then_promo():
    urls = [
        "/media/promo_frame_x.jpg",
        "/media/studio_polish/x/ai_creative_neon_a.jpg",
        "/media/studio_polish/x/studio_white_b.jpg",
        "/media/studio_polish/x/channel_story_c.jpg",
        "/media/studio_polish/x/ai_lifestyle_d.jpg",
        "/media/studio_polish/x/preflight_relight_e.jpg",
    ]
    out = curate_reel_image_urls(urls)
    assert "channel_story" in out[0]
    assert "studio_white" in out[1]
    assert out[-1] == "/media/promo_frame_x.jpg"
    assert not any("preflight" in u for u in out)


def test_curate_caps_ai_scenes_at_three():
    urls = [
        "/media/studio_white.jpg",
        "/media/ai_creative_splash.jpg",
        "/media/ai_creative_marble.jpg",
        "/media/ai_creative_neon.jpg",
        "/media/ai_lifestyle.jpg",
        "/media/ai_lifestyle_alt.jpg",
    ]
    out = curate_reel_image_urls(urls, max_slides=10)
    ai_count = sum(1 for u in out if "ai_" in u)
    assert ai_count == 3
