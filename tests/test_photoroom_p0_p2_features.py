"""Photoroom P0–P2 feature wiring tests."""

from unittest.mock import MagicMock, patch

import pytest

from apps.products.asset_pack import build_asset_pack
from apps.products.photoroom_plus import FRAGILE_HD_CATEGORIES, hd_cutout_headers_for_product
from apps.products.photoroom_preflight import REPAIR_ORDER, build_repair_plan
from apps.products.photoroom_review import post_blocked_by_alteration_review
from apps.products.reel_curation import curate_reel_image_urls, story_export_urls


def test_story_export_urls_prefers_uncrop():
    urls = [
        "/media/studio_polish/x/channel_story_a.jpg",
        "/media/studio_polish/x/channel_story_uncrop_b.jpg",
    ]
    out = story_export_urls(urls)
    assert "uncrop" in out[0]
    assert len(out) == 2


def test_curate_prepends_story_heroes():
    urls = [
        "/media/studio_polish/x/studio_white.jpg",
        "/media/studio_polish/x/ai_scene_table.jpg",
        "/media/studio_polish/x/channel_story_uncrop.jpg",
        "/media/studio_polish/x/channel_story.jpg",
    ]
    out = curate_reel_image_urls(urls, max_slides=4)
    assert "channel_story" in out[0]


def test_repair_order_includes_ai_ironing_for_apparel():
    assert "ai_ironing" in REPAIR_ORDER
    assert REPAIR_ORDER.index("ai_ironing") == REPAIR_ORDER.index("photofix") + 1


def test_build_repair_plan_apparel_ironing():
    from apps.products.photoroom_preflight import PhotoQualityReport

    report = PhotoQualityReport(lighting="uneven", sharpness="soft")
    plan = build_repair_plan(
        report,
        plan_tier="pro",
        commerce_source="snap",
        category="apparel",
    )
    assert "ai_ironing" in plan


def test_hd_cutout_headers_for_jewelry():
    product = MagicMock()
    product.name = "Gold ring"
    product.tags = ["jewelry"]
    with patch("apps.products.photoroom_plus.detect_product_category", return_value="jewelry"):
        headers = hd_cutout_headers_for_product(product, {})
    assert headers.get("pr-hd-background-removal") == "auto"
    assert "jewelry" in FRAGILE_HD_CATEGORIES


def test_post_blocked_by_alteration_review():
    post = MagicMock()
    product = MagicMock()
    post.product = product
    with patch(
        "apps.products.photoroom_review.review_state_for_product",
        return_value={
            "alteration_review_required": True,
            "review_pending_count": 1,
            "review_pending": [{"label": "Ghost mannequin", "variant": "ghost_mannequin"}],
        },
    ):
        blocked, reason = post_blocked_by_alteration_review(post)
    assert blocked is True
    assert "approval" in reason.lower()


def test_asset_pack_groups():
    product = MagicMock()
    product.all_image_urls = [
        "/media/product_images/raw.jpg",
        "/media/studio_polish/x/studio_white.jpg",
        "/media/studio_polish/x/channel_story.jpg",
        "/media/studio_polish/x/channel_marketplace_white.png",
    ]
    with patch(
        "apps.products.gallery_preferences.filter_gallery_urls",
        side_effect=lambda urls, _p: urls,
    ):
        groups = build_asset_pack(product)
    ids = [g.id for g in groups]
    assert "feed" in ids
    assert "story" in ids
    assert "marketplace" in ids
    assert "original" in ids


@pytest.mark.django_db
def test_video_animate_limits_pro(user):
    from apps.billing.video_credits import get_video_animate_limits

    user.profile.plan = "pro"
    user.profile.save(update_fields=["plan"])
    limits = get_video_animate_limits(user)
    assert limits["max"] == 15
    assert limits["enabled"] is True
