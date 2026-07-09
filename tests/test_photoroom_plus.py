"""Tests for Photoroom Plus variant selection."""

from apps.products.photoroom_plus import (
    COMMERCE_SCENE_VARIANT_IDS,
    DEPRECATED_CREATIVE_VARIANT_IDS,
    EDIT_WITH_AI_PRODUCT_STAGING_BASE,
    PLUS_VARIANT_CATALOG,
    build_commerce_scene_prompt,
    build_creative_prompt,
    build_edit_ai_angle_prompt,
    build_edit_ai_staging_prompt,
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


def test_apparel_gets_mannequin_on_pro():
    p = _Product(name="Summer Dress", tags=["fashion", "apparel"])
    specs = select_plus_variants(p, {}, plan_tier="pro", max_count=8)
    ids = {s.id for s in specs}
    assert "ghost_mannequin" in ids


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
    assert "virtual_model_hold" in ids
    assert "virtual_model_adorn" in ids
    assert "beautify_nocutout" in ids
    assert "relight" in ids
    assert "beautify" in ids
    assert "upscale" in ids
    assert "ai_touchup" in ids
    assert "edit_ai_staging" in ids
    assert "edit_ai_angle" in ids
    assert "digital_desk_hero" in ids
    assert "digital_device_mockup" in ids


def test_channel_export_specs_in_catalog():
    ids = set(PLUS_VARIANT_CATALOG)
    assert "channel_story" in ids
    assert "channel_banner" in ids
    assert "channel_story_uncrop" in ids
    assert "channel_marketplace" in ids
    assert "channel_marketplace_jpeg" in ids


def test_marketplace_variant_google_shopping_params():
    png = PLUS_VARIANT_CATALOG["channel_marketplace"]
    jpeg = PLUS_VARIANT_CATALOG["channel_marketplace_jpeg"]
    assert png.params["background.color"] == "FFFFFF"
    assert png.params["outputSize"] == "1000x1000"
    assert png.params["export.format"] == "png"
    assert float(png.params["padding"]) == 0.075
    assert jpeg.params["export.format"] == "jpeg"
    assert png.pack_eligible is False


def test_marketplace_slide_role():
    from apps.products.photoroom_plus import slide_role_for_variant

    assert slide_role_for_variant("channel_marketplace", "product", "general") == "marketplace"
    assert slide_role_for_variant("channel_marketplace_jpeg", "product", "beauty") == "marketplace"


def test_brand_hero_first_when_template_enabled():
    from apps.products.photoroom_brand_template import PhotoroomBrandTemplate
    from apps.products.photoroom_plus import order_variants_by_slide_role

    template = PhotoroomBrandTemplate(
        enabled=True,
        shadow_mode="ai.soft",
        padding="0.08",
        ai_background_seed=117879368,
        outline_color_hex="000000",
        studio_color_hex="E8D5B7",
        style_suffix="warm boutique",
    )
    candidates = [
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["studio_brand"],
    ]
    ordered = order_variants_by_slide_role(
        candidates,
        offering="product",
        category="apparel",
        max_count=3,
        hero_studio_ids=("studio_brand", "studio_white"),
    )
    assert ordered[0].id == "studio_brand"


def test_select_variants_brand_hero_with_profile_colors():
    from apps.products.photoroom_brand_template import PhotoroomBrandTemplate

    p = _Product(name="Kitenge Dress", tags=["fashion"])
    template = PhotoroomBrandTemplate(
        enabled=True,
        shadow_mode="ai.soft",
        padding="0.08",
        ai_background_seed=117879368,
        outline_color_hex="000000",
        studio_color_hex="C4A882",
        style_suffix="",
    )
    specs = select_plus_variants(
        p,
        {},
        plan_tier="growth",
        max_count=4,
        brand_template=template,
        brand_colors={"primary": "#C4A882"},
    )
    assert specs[0].id == "studio_brand"


def test_relight_mode_resolved_for_products():
    from apps.products.photoroom_plus import resolve_variant_params

    p = _Product(name="USB Hub", tags=["electronics"])
    spec = PLUS_VARIANT_CATALOG["relight"]
    params = resolve_variant_params(spec, p, {}, {})
    assert params["lighting.mode"] == "ai.preserve-hue-and-saturation"


def test_relight_mode_auto_for_services():
    from apps.products.photoroom_plus import resolve_variant_params

    p = _Product(name="Home Cleaning", offering_type="service")
    spec = PLUS_VARIANT_CATALOG["relight"]
    params = resolve_variant_params(spec, p, {}, {})
    assert params["lighting.mode"] == "ai.auto"


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


def test_apparel_proof_prefers_flat_lay_then_ghost():
    from apps.products.photoroom_plus import order_variants_by_slide_role

    candidates = [
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["flat_lay"],
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
    assert "flat_lay" in ids or "ghost_mannequin" in ids or "virtual_model" in ids


def test_capability_for_variant_taxonomy():
    from apps.products.photoroom_plus import (
        CAPABILITY_AI_BACKGROUND,
        CAPABILITY_BEAUTIFY,
        CAPABILITY_FLAT_LAY,
        CAPABILITY_STUDIO,
        capability_for_variant,
    )

    assert capability_for_variant("studio_white") == CAPABILITY_STUDIO
    assert capability_for_variant("ai_scene_table") == CAPABILITY_AI_BACKGROUND
    assert capability_for_variant("beautify_nocutout") == CAPABILITY_BEAUTIFY
    assert capability_for_variant("flat_lay") == CAPABILITY_FLAT_LAY


def test_apparel_5pack_balanced_mix():
    """Growth 5-pack: studio hero + ≥2 AI backgrounds + flat_lay polish."""
    from apps.products.photoroom_plus import (
        capability_for_variant,
        CAPABILITY_AI_BACKGROUND,
        CAPABILITY_STUDIO,
    )

    p = _Product(name="Kitenge Dress", tags=["fashion", "apparel"])
    specs = select_plus_variants(p, {}, plan_tier="growth", max_count=5, uncertainty_score=0.1)
    ids = [s.id for s in specs]
    caps = [capability_for_variant(s.id) for s in specs]

    assert caps[0] == CAPABILITY_STUDIO or ids[0].startswith("studio_")
    assert caps.count(CAPABILITY_AI_BACKGROUND) >= 2
    assert "flat_lay" in ids
    assert len(set(ids)) == len(ids)


def test_food_5pack_prefers_beautify_not_flat_lay_first():
    p = _Product(name="Chicken Biryani", tags=["food", "restaurant"])
    specs = select_plus_variants(
        p,
        {"photo_quality": {"lighting": "good", "sharpness": "sharp"}},
        plan_tier="growth",
        max_count=5,
        commerce_source="snap",
        uncertainty_score=0.1,
    )
    ids = [s.id for s in specs]
    assert any(x in ids for x in ("beautify_nocutout", "beautify"))
    # Flat lay must not crowd out beautify as the polish pick
    if "flat_lay" in ids and "beautify_nocutout" in ids:
        assert ids.index("beautify_nocutout") < ids.index("flat_lay")


def test_high_uncertainty_skips_flat_lay_and_ghost():
    from apps.products.photoroom_plus import order_variants_by_slide_role

    candidates = [
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["ai_scene_table"],
        PLUS_VARIANT_CATALOG["flat_lay"],
        PLUS_VARIANT_CATALOG["ghost_mannequin"],
        PLUS_VARIANT_CATALOG["relight"],
        PLUS_VARIANT_CATALOG["beautify"],
    ]
    ordered = order_variants_by_slide_role(
        candidates,
        offering="product",
        category="apparel",
        max_count=5,
        uncertainty_score=0.85,
    )
    ids = [s.id for s in ordered]
    assert "flat_lay" not in ids
    assert "ghost_mannequin" not in ids
    assert ids[0] == "studio_white"


def test_no_duplicate_beautify_family_in_pack():
    from apps.products.photoroom_plus import (
        BEAUTIFY_FAMILY_IDS,
        enforce_pack_capability_balance,
    )

    picked = [
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["ai_scene_table"],
        PLUS_VARIANT_CATALOG["beautify"],
        PLUS_VARIANT_CATALOG["beautify_nocutout"],
    ]
    balanced = enforce_pack_capability_balance(
        picked,
        picked,
        max_count=5,
        category="food",
        offering="product",
        uncertainty_score=0.1,
    )
    beautify_ids = [s.id for s in balanced if s.id in BEAUTIFY_FAMILY_IDS]
    assert len(beautify_ids) <= 1


def test_filter_carousel_urls_excludes_channel():
    from apps.products.photoroom_plus import filter_carousel_urls

    urls = [
        "/media/studio_polish/x/studio_white_abc.jpg",
        "/media/studio_polish/x/channel_story_def.jpg",
        "/media/studio_polish/x/channel_marketplace_abc.png",
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
    # Index 0 is centered (uses padding); index 1+ use directional padding*
    assert "padding" in a or a.get("paddingLeft")
    assert b.get("paddingLeft") or b.get("horizontalAlignment") != a.get("horizontalAlignment")


def test_studio_white_layout_rotates():
    from apps.products.photoroom_plus import apply_variant_layout

    base = {"padding": "0.12", "scaling": "fill"}
    out = apply_variant_layout(base, "studio_white", 2)
    assert out.get("verticalAlignment") == "top"
    assert "paddingLeft" in out
    assert "padding" not in out


def test_ai_scene_variants_use_default_prompt_expansion():
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG

    for vid in ("ai_lifestyle_alt", "ai_scene_table", "ai_creative_marble"):
        params = PLUS_VARIANT_CATALOG[vid].params
        assert "background.expandPrompt" not in params
        assert params.get("background.expandPrompt.mode") != "ai.never"


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
    # Safety clause may say "no water splash…" — ensure we are not requesting a splash scene
    assert "water splash," in prompt.lower() or "no water splash" in prompt.lower()
    assert not prompt.lower().startswith("water splash")


def test_deprecated_splash_prompt_unchanged_for_manual_use():
    p = _Product(name="Mango Juice", tags=["food", "drink"])
    prompt = build_creative_prompt("ai_creative_splash", p, {"campaign_angle": "refreshing"})
    assert "water splash" in prompt.lower()


def test_commerce_slide_role_tag():
    from apps.products.photoroom_plus import slide_role_for_variant

    assert slide_role_for_variant("ai_scene_table", "product", "apparel") == "commerce"
    assert slide_role_for_variant("ai_creative_marble", "product", "beauty") == "creative"
    assert slide_role_for_variant("studio_white", "product", "beauty") == "hero"
    assert slide_role_for_variant("edit_ai_staging", "product", "beauty") == "lifestyle_edit"


def test_edit_ai_staging_prompt_uses_official_recipe():
    p = _Product(name="Amaya Speaker", tags=["electronics"])
    prompt = build_edit_ai_staging_prompt(p, {"campaign_angle": "deep bass"})
    assert EDIT_WITH_AI_PRODUCT_STAGING_BASE in prompt
    assert "Amaya Speaker" in prompt
    assert "fully visible" in prompt.lower()


def test_edit_ai_angle_prompt_mentions_product():
    p = _Product(name="Amaya Speaker", tags=["electronics"])
    prompt = build_edit_ai_angle_prompt(p, {})
    assert "Amaya Speaker" in prompt
    assert "different angle" in prompt.lower()


def test_growth_pack_includes_edit_with_ai_on_pro_budget():
    p = _Product(name="Amaya Speaker", tags=["electronics", "bluetooth"])
    specs = select_plus_variants(
        p, {"campaign_angle": "portable"}, plan_tier="pro", max_count=7,
    )
    ids = [s.id for s in specs]
    assert "edit_ai_staging" in ids or "edit_ai_angle" in ids


def test_starter_plan_excludes_edit_with_ai():
    p = _Product(name="Serum", tags=["beauty"])
    specs = select_plus_variants(p, {}, plan_tier="starter", max_count=10)
    ids = [s.id for s in specs]
    assert "edit_ai_staging" not in ids
    assert "edit_ai_angle" not in ids


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
        assert params.get("removeBackground") == "false"
        assert "shadow.mode" not in params
        assert "padding" not in params
        assert params.get("scaling") in ("fit", "fill")


# ── P1-1 vertical packs v2 ───────────────────────────────────────────────────


def test_jewelry_vertical_pack_prefers_dark_studio():
    p = _Product(name="Gold Hoop Earrings", tags=["jewelry", "gold"])
    specs = select_plus_variants(p, {}, plan_tier="growth", max_count=6)
    ids = [s.id for s in specs]
    assert ids[0] == "studio_dark"
    assert "ai_creative_marble" in ids


def test_electronics_vertical_pack_includes_color_safe_relight():
    p = _Product(name="USB-C Charger", tags=["electronics", "tech"])
    specs = select_plus_variants(p, {}, plan_tier="growth", max_count=5)
    ids = [s.id for s in specs]
    assert "relight" in ids
    assert "ai_creative_podium" in ids or "ai_scene_table" in ids


def test_mitumba_apparel_flat_lay_starter_no_ghost():
    p = _Product(name="Mitumba Denim Jacket", tags=["mitumba", "fashion"])
    specs = select_plus_variants(p, {}, plan_tier="starter", max_count=6)
    ids = [s.id for s in specs]
    assert "flat_lay" in ids
    assert "ghost_mannequin" not in ids


def test_mitumba_apparel_pro_includes_ghost_with_review():
    from apps.products.photoroom_review import needs_alteration_review

    p = _Product(name="Preloved Summer Dress", tags=["thrift", "dress"])
    specs = select_plus_variants(p, {}, plan_tier="pro", max_count=6)
    ids = [s.id for s in specs]
    assert "flat_lay" in ids
    assert "ghost_mannequin" in ids
    flagged, reason = needs_alteration_review("ghost_mannequin")
    assert flagged is True


def test_vision_product_category_hint_resolves_vertical():
    from apps.products.scene_packs import resolve_scene_vertical

    p = _Product(name="Item", tags=[])
    vertical = resolve_scene_vertical(
        p,
        {"product_category": "electronics"},
    )
    assert vertical == "electronics"


def test_jewelry_locked_seed_applied_in_params():
    from apps.products.photoroom_plus import resolve_variant_params

    p = _Product(name="Silver Ring", tags=["jewelry"])
    spec = PLUS_VARIANT_CATALOG["ai_creative_marble"]
    params = resolve_variant_params(spec, p, {}, {})
    assert params["background.seed"] == "33120477"


# ── P1-6 AI scene intelligence ───────────────────────────────────────────────


def test_low_quality_photo_reduces_ai_scene_count():
    from apps.products.photoroom_plus import _target_ai_scene_count

    high = _target_ai_scene_count(6, analysis={}, category="beauty")
    low = _target_ai_scene_count(
        6,
        analysis={"photo_quality": {"sharpness": "blurry", "lighting": "dark"}},
        category="beauty",
    )
    assert low < high


def test_multi_angles_boosts_edit_ai_angle_in_proof():
    from apps.products.photoroom_plus import order_variants_by_slide_role

    candidates = [
        PLUS_VARIANT_CATALOG["studio_white"],
        PLUS_VARIANT_CATALOG["ai_lifestyle"],
        PLUS_VARIANT_CATALOG["edit_ai_angle"],
        PLUS_VARIANT_CATALOG["relight"],
    ]
    ordered = order_variants_by_slide_role(
        candidates,
        offering="product",
        category="electronics",
        max_count=4,
        analysis={"multi_image_angles": ["front", "side", "detail"]},
    )
    ids = [s.id for s in ordered]
    assert "edit_ai_angle" in ids


def test_stall_wholesale_brief_reduces_ai_scenes():
    from apps.products.photoroom_plus import _target_ai_scene_count

    normal = _target_ai_scene_count(6, category="apparel")
    wholesale = _target_ai_scene_count(
        6,
        category="apparel",
        stall_context={"campaign_tone": "wholesale"},
    )
    assert wholesale <= normal


def test_food_analysis_prefers_food_surfaces():
    p = _Product(name="Samosas", tags=["food"])
    specs = select_plus_variants(
        p,
        {"photo_quality": {"lighting": "good", "sharpness": "sharp"}},
        plan_tier="growth",
        max_count=5,
        commerce_source="snap",
    )
    ids = [s.id for s in specs]
    assert any(vid.startswith("food_surface_") for vid in ids)


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


def test_normalize_photoroom_edit_params_shadow_and_expand():
    from apps.products.photoroom_api import normalize_photoroom_edit_params

    out = normalize_photoroom_edit_params({
        "shadow.mode": "ai.soft",
        "background.expandPrompt": "ai.auto",
        "removeBackground": "true",
    })
    assert out["shadow.mode"] == "ai.preset-soft"
    assert "background.expandPrompt" not in out
    assert "background.expandPrompt.mode" not in out

    never = normalize_photoroom_edit_params({
        "background.expandPrompt": "ai.never",
        "shadow.mode": "ai.hard",
    })
    assert never["background.expandPrompt.mode"] == "ai.never"
    assert never["shadow.mode"] == "ai.preset-hard"
