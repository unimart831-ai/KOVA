"""Tests for Photoroom preflight repair planning (Phase A/B)."""

from apps.products.photoroom_preflight import (
    PhotoQualityReport,
    assess_photo_quality,
    build_repair_plan,
    channel_export_budget,
    select_channel_variant_ids,
)


def test_build_repair_plan_dark_and_blurry():
    report = PhotoQualityReport(
        lighting="dark",
        sharpness="blurry",
        has_distracting_text=False,
        crop="comfortable",
    )
    plan = build_repair_plan(report, plan_tier="growth")
    assert plan[0] == "relight"
    assert "upscale" in plan


def test_build_repair_plan_text_first():
    report = PhotoQualityReport(
        lighting="dark",
        sharpness="blurry",
        has_distracting_text=True,
        crop="very_tight",
    )
    plan = build_repair_plan(report, plan_tier="growth")
    assert plan[0] == "text_removal"
    assert "uncrop" in plan


def test_starter_skips_uncrop():
    report = PhotoQualityReport(crop="very_tight")
    plan = build_repair_plan(report, plan_tier="starter")
    assert "uncrop" not in plan


def test_assess_merges_vision_photo_quality():
    analysis = {
        "photo_quality": {
            "lighting": "uneven",
            "sharpness": "soft",
            "has_distracting_text": True,
            "crop": "tight",
        }
    }
    report = assess_photo_quality("https://example.com/photo.jpg", analysis)
    assert report.lighting == "uneven"
    assert report.has_distracting_text is True
    assert "text_removal" in report.repair_plan


def test_channel_export_budget_growth():
    assert channel_export_budget("growth") == 2
    assert channel_export_budget("starter") == 0


def test_select_channel_variant_portrait_uses_uncrop():
    ids = select_channel_variant_ids(0.6)
    assert ids[0] == "channel_story_uncrop"


def test_select_channel_variant_square_uses_expand():
    ids = select_channel_variant_ids(1.0)
    assert ids[0] == "channel_story"


def test_channel_variants_not_in_scene_pack():
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, select_plus_variants

    class P:
        name = "Test"
        tags = []
        offering_type = "product"

    specs = select_plus_variants(P(), {}, plan_tier="agency", max_count=20)
    ids = {s.id for s in specs}
    assert "channel_story" not in ids
    assert "channel_banner" not in ids
    assert "channel_story" in PLUS_VARIANT_CATALOG
