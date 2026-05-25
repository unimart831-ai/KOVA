"""Tests for Photoroom Plus variant selection."""

from apps.products.photoroom_plus import (
    PLUS_VARIANT_CATALOG,
    build_lifestyle_prompt,
    detect_product_category,
    select_plus_variants,
)


class _Product:
    def __init__(self, name="Test", tags=None, offering_type="product"):
        self.name = name
        self.tags = tags or []
        self.offering_type = offering_type


def test_detect_apparel_category():
    p = _Product(name="Blue Cotton Shirt", tags=["fashion"])
    assert detect_product_category(p, {}) == "apparel"


def test_select_variants_includes_studio_and_lifestyle():
    p = _Product(name="USB Cable", tags=["electronics"])
    specs = select_plus_variants(p, {}, plan_tier="starter", max_count=5)
    ids = [s.id for s in specs]
    assert "studio_white" in ids
    assert "ai_lifestyle" in ids


def test_apparel_gets_mannequin_or_model():
    p = _Product(name="Summer Dress", tags=["fashion", "apparel"])
    specs = select_plus_variants(p, {}, plan_tier="growth", max_count=8)
    ids = {s.id for s in specs}
    assert "ghost_mannequin" in ids or "virtual_model" in ids


def test_starter_plan_excludes_pro_only_variants():
    p = _Product(name="Serum", tags=["beauty"])
    specs = select_plus_variants(p, {}, plan_tier="starter", max_count=10)
    ids = {s.id for s in specs}
    assert "text_removal" not in ids
    assert "upscale" not in ids


def test_service_offering_uses_service_variants():
    p = _Product(name="Home Cleaning", offering_type="service")
    specs = select_plus_variants(p, {"campaign_angle": "trusted local pros"}, plan_tier="growth", max_count=4)
    ids = {s.id for s in specs}
    assert "service_hero" in ids
    assert "ghost_mannequin" not in ids
    assert "digital_desk_hero" not in ids


def test_digital_offering_uses_digital_variants():
    p = _Product(name="Notion Template Pack", offering_type="digital")
    specs = select_plus_variants(p, {"campaign_angle": "productivity boost"}, plan_tier="growth", max_count=4)
    ids = {s.id for s in specs}
    assert "digital_desk_hero" in ids
    assert "digital_device_mockup" in ids
    assert "service_hero" not in ids
    assert "ghost_mannequin" not in ids


def test_lifestyle_prompt_mentions_product():
    p = _Product(name="Amara Lotion", tags=["beauty"])
    prompt = build_lifestyle_prompt(p, {"campaign_angle": "glow"}, variant="primary")
    assert "Amara Lotion" in prompt or "lotion" in prompt.lower()


def test_catalog_covers_plus_feature_groups():
    ids = set(PLUS_VARIANT_CATALOG)
    assert "ai_lifestyle" in ids
    assert "flat_lay" in ids
    assert "ghost_mannequin" in ids
    assert "virtual_model" in ids
    assert "relight" in ids
    assert "beautify" in ids
    assert "upscale" in ids
    assert "ai_touchup" in ids
    assert "digital_desk_hero" in ids
    assert "digital_device_mockup" in ids


def test_channel_export_specs_in_catalog():
    ids = set(PLUS_VARIANT_CATALOG)
    assert "channel_story" in ids
    assert "channel_banner" in ids
    assert "channel_story_uncrop" in ids


def test_slide_role_order_starts_with_hero():
    from apps.products.photoroom_plus import order_variants_by_slide_role

    candidates = [
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["relight"],
        PLUS_VARIANT_CATALOG["background_blur"],
    ]
    ordered = order_variants_by_slide_role(
        candidates,
        offering="product",
        category="electronics",
        max_count=4,
    )
    assert ordered[0].id == "studio_white"
    assert ordered[1].id == "ai_lifestyle"


def test_apparel_proof_prefers_ghost_mannequin():
    from apps.products.photoroom_plus import order_variants_by_slide_role

    candidates = [
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["ghost_mannequin"],
        PLUS_VARIANT_CATALOG["virtual_model"],
    ]
    ordered = order_variants_by_slide_role(
        candidates,
        offering="product",
        category="apparel",
        max_count=4,
    )
    ids = [s.id for s in ordered]
    assert ids[0] == "studio_white"
    assert "ghost_mannequin" in ids or "virtual_model" in ids


def test_filter_carousel_urls_excludes_channel():
    from apps.products.photoroom_plus import filter_carousel_urls

    urls = [
        "/media/studio_polish/x/studio_white_abc.jpg",
        "/media/studio_polish/x/channel_story_def.jpg",
        "/media/studio_polish/x/preflight_relight_ghi.jpg",
    ]
    filtered = filter_carousel_urls(urls)
    assert len(filtered) == 1
    assert "studio_white" in filtered[0]
