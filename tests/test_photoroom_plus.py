"""Tests for Photoroom Plus variant selection."""

from apps.products.photoroom_plus import (
    COMMERCE_SCENE_VARIANT_IDS,
    DEPRECATED_CREATIVE_VARIANT_IDS,
    PLUS_VARIANT_CATALOG,
    build_commerce_scene_prompt,
    build_creative_prompt,
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


def test_detect_sneaker_as_apparel():
    p = _Product(name="Stylish High-Top Sneaker", tags=["footwear"])
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


def test_lifestyle_prompt_mentions_product_and_visibility_rules():
    p = _Product(name="Amara Lotion", tags=["beauty"])
    prompt = build_lifestyle_prompt(p, {"campaign_angle": "glow"}, variant="primary")
    assert "Amara Lotion" in prompt or "lotion" in prompt.lower()
    assert "fully visible" in prompt.lower()
    assert "no water splash" in prompt.lower()


def test_catalog_covers_plus_feature_groups():
    ids = set(PLUS_VARIANT_CATALOG)
    assert "ai_lifestyle" in ids
    assert "ai_scene_table" in ids
    assert "ai_scene_shelf" in ids
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


def test_filter_shop_gallery_urls_excludes_promo_frame():
    from apps.products.photoroom_plus import filter_shop_gallery_urls

    urls = [
        "/media/studio_polish/x/studio_white_abc.jpg",
        "/media/studio_polish/x/promo_frame_def.jpg",
        "/media/studio_polish/x/ai_scene_table_ghi.jpg",
    ]
    filtered = filter_shop_gallery_urls(urls)
    assert len(filtered) == 2
    assert not any("promo_frame" in u for u in filtered)


def test_beauty_gets_commerce_table_not_splash():
    p = _Product(name="Glow Serum", tags=["beauty", "skincare"])
    specs = select_plus_variants(p, {"campaign_angle": "radiant glow"}, plan_tier="growth", max_count=4)
    ids = [s.id for s in specs]
    assert ids[0] == "studio_white"
    assert "ai_scene_table" in ids
    assert "ai_creative_splash" not in ids


def test_apparel_gets_table_and_shelf_not_neon():
    p = _Product(name="High-Top Sneaker", tags=["footwear", "sneaker"])
    specs = select_plus_variants(p, {}, plan_tier="growth", max_count=5)
    ids = [s.id for s in specs]
    assert "ai_scene_table" in ids or "ai_scene_retail" in ids
    assert "ai_creative_neon" not in ids
    assert "ai_creative_splash" not in ids


def test_beauty_gets_multiple_ai_scenes_with_budget():
    p = _Product(name="Glow Serum", tags=["beauty", "skincare"])
    specs = select_plus_variants(p, {"campaign_angle": "radiant glow"}, plan_tier="growth", max_count=5)
    ids = [s.id for s in specs]
    ai_ids = [i for i in ids if i.startswith("ai_")]
    assert len(ai_ids) >= 2


def test_apply_variant_layout_shifts_ai_scenes():
    from apps.products.photoroom_plus import apply_variant_layout

    base = {"padding": "0.12", "background.prompt": "test"}
    a = apply_variant_layout(base, "ai_scene_table", 0)
    b = apply_variant_layout(base, "ai_scene_table", 1)
    assert a["horizontalAlignment"] != b.get("horizontalAlignment", "center") or a.get("padding") != b.get("padding")
    assert "padding" not in a or a.get("paddingLeft")


def test_studio_white_layout_rotates():
    from apps.products.photoroom_plus import apply_variant_layout

    base = {"padding": "0.12", "scaling": "fill"}
    out = apply_variant_layout(base, "studio_white", 2)
    assert out.get("verticalAlignment") == "top"
    assert "paddingLeft" in out
    assert "padding" not in out


def test_ai_scene_variants_include_expand_prompt():
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG

    for vid in ("ai_lifestyle_alt", "ai_scene_table", "ai_creative_marble"):
        assert PLUS_VARIANT_CATALOG[vid].params.get("background.expandPrompt") == "ai.auto"


def test_commerce_table_prompt_for_sneaker():
    p = _Product(name="High-Top Sneaker", tags=["footwear"])
    prompt = build_commerce_scene_prompt("ai_scene_table", p, {})
    assert "table" in prompt.lower() or "surface" in prompt.lower()
    assert "High-Top Sneaker" in prompt
    assert "fully visible" in prompt.lower()


def test_marble_prompt_is_commerce_safe():
    p = _Product(name="Glow Serum", tags=["beauty"])
    prompt = build_creative_prompt("ai_creative_marble", p, {"campaign_angle": "radiant"})
    assert "marble" in prompt.lower()
    assert "fully visible" in prompt.lower()
    assert "water splash" not in prompt.lower()


def test_deprecated_splash_prompt_unchanged_for_manual_use():
    p = _Product(name="Mango Juice", tags=["food", "drink"])
    prompt = build_creative_prompt("ai_creative_splash", p, {"campaign_angle": "refreshing"})
    assert "water splash" in prompt.lower()


def test_commerce_slide_role_tag():
    from apps.products.photoroom_plus import slide_role_for_variant

    assert slide_role_for_variant("ai_scene_table", "product", "apparel") == "commerce"
    assert slide_role_for_variant("ai_creative_marble", "product", "beauty") == "creative"
    assert slide_role_for_variant("studio_white", "product", "beauty") == "hero"


def test_starter_plan_excludes_commerce_scenes_and_creative_variants():
    p = _Product(name="Serum", tags=["beauty"])
    specs = select_plus_variants(p, {}, plan_tier="starter", max_count=10)
    ids = {s.id for s in specs}
    assert "ai_creative_splash" not in ids
    assert "ai_scene_table" not in ids


def test_deprecated_creatives_not_pack_eligible():
    for vid in DEPRECATED_CREATIVE_VARIANT_IDS:
        assert PLUS_VARIANT_CATALOG[vid].pack_eligible is False


def test_commerce_scene_variants_in_catalog():
    for vid in COMMERCE_SCENE_VARIANT_IDS:
        assert vid in PLUS_VARIANT_CATALOG
        assert PLUS_VARIANT_CATALOG[vid].pack_eligible is True


def test_channel_exports_omit_cutout_stack():
    """expand/uncrop on polished heroes must not send removeBackground + shadow."""
    for vid in ("channel_story", "channel_story_uncrop", "channel_banner"):
        params = PLUS_VARIANT_CATALOG[vid].params
        assert "removeBackground" not in params
        assert "shadow.mode" not in params
        assert "padding" not in params
        assert params.get("scaling") == "fit"


def test_strip_conflicting_edit_params():
    from apps.products.photoroom_plus import _strip_conflicting_edit_params

    raw = {
        "expand.mode": "ai.auto",
        "removeBackground": "true",
        "shadow.mode": "ai.soft",
        "outputSize": "1080x1920",
    }
    stripped = _strip_conflicting_edit_params(raw)
    assert stripped == {"expand.mode": "ai.auto", "outputSize": "1080x1920"}
