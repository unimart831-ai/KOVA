"""Tests for reel image curation."""

from apps.products.reel_curation import curate_reel_image_urls


def test_curate_orders_story_then_ai():
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
    if any("promo_frame" in u for u in out):
        assert "promo_frame" in out[-1]
    assert not any("preflight" in u for u in out)


def test_curate_max_pool_for_director():
    urls = [f"/media/ai_scene_{i}.jpg" for i in range(8)]
    urls.append("/media/studio_white.jpg")
    out = curate_reel_image_urls(urls, max_slides=5)
    assert len(out) <= 10


def test_curate_prioritizes_edit_ai():
    urls = [
        "/media/studio_white.jpg",
        "/media/edit_ai_staging.jpg",
        "/media/edit_ai_angle.jpg",
        "/media/ai_lifestyle.jpg",
    ]
    out = curate_reel_image_urls(urls, max_slides=5)
    assert out[0] == "/media/studio_white.jpg"
    assert "/media/edit_ai_staging.jpg" in out
    assert "/media/edit_ai_angle.jpg" in out


def test_curate_caps_ai_scenes_at_two():
    urls = [
        "/media/studio_white.jpg",
        "/media/ai_scene_table.jpg",
        "/media/ai_scene_shelf.jpg",
        "/media/ai_creative_marble.jpg",
        "/media/ai_lifestyle.jpg",
        "/media/ai_lifestyle_alt.jpg",
    ]
    out = curate_reel_image_urls(urls, max_slides=10)
    ai_count = sum(1 for u in out if "ai_" in u)
    assert ai_count == 2


def test_curate_prefers_polished_over_raw_snap():
    urls = [
        "/media/product_images/snap_original.jpg",
        "/media/studio_polish/x/studio_white.jpg",
        "/media/studio_polish/x/ai_lifestyle.jpg",
    ]
    out = curate_reel_image_urls(urls)
    assert "/media/product_images/snap_original.jpg" not in out
    assert "/media/studio_polish/x/studio_white.jpg" in out
