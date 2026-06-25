"""Professional reel studio — curation, role-aware copy, sanitization."""

from apps.content.reel_studio import (
    filter_reel_sources,
    sanitize_hooks_for_roles,
)
from apps.products.reel_curation import curate_reel_image_urls


def test_filter_reel_sources_excludes_carousels():
    urls = [
        "/media/carousels/abc/slide_1.jpg",
        "/media/studio_polish/x/composition_hero_a.jpg",
        "/media/studio_polish/x/channel_story_b.jpg",
        "/media/studio_polish/x/studio_white_c.jpg",
    ]
    out = filter_reel_sources(urls)
    assert not any("carousels" in u for u in out)
    assert out[0].endswith("composition_hero_a.jpg")


def test_sanitize_hooks_strips_hero_slide_copy():
    hooks = ["Hook line", "Price on hero", "", "", "KES 500\nShop"]
    roles = ["hook", "hero", "desire", "desire", "cta"]
    clean = sanitize_hooks_for_roles(hooks, roles)
    assert clean[0] == "Hook line"
    assert clean[1] == ""
    assert "KES 500" in clean[4]


def test_curation_excludes_catalog_carousel_markers():
    urls = [
        "/media/catalog_carousel/slide.jpg",
        "/media/studio_polish/x/channel_story.jpg",
    ]
    assert curate_reel_image_urls(urls) == [urls[1]]
