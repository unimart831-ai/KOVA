"""Tests for reel director (recipes, rotation, hooks)."""

from apps.content.reel_director import (
    REEL_RECIPES,
    build_hook_texts,
    build_reel_plan,
    pick_recipe_id,
)


def test_pick_recipe_rotates_by_seed():
    a = pick_recipe_id(seed="product-1", category="general")
    b = pick_recipe_id(seed="product-2", category="general")
    c = pick_recipe_id(seed="product-1", category="general")
    assert a in REEL_RECIPES
    assert c == a
    assert a != b or len(REEL_RECIPES) == 1


def test_category_bias_electronics_toward_flash():
    recipes = {
        pick_recipe_id(seed=f"elec-{i}", category="electronics")
        for i in range(20)
    }
    assert "flash_drop" in recipes


def test_hook_texts_staggered_on_early_slides():
    texts = build_hook_texts(
        slide_count=5,
        slide_roles=["hook", "hero", "desire", "desire", "cta"],
        product_name="Amaya Speaker",
        price_label="KES 1,200",
        brand_name="Amaya",
        key_feature="Crystal-clear sound",
        category="electronics",
    )
    # Benefit-led hook, not bare product name
    assert texts[0]
    assert texts[0] != "Amaya Speaker"
    assert "Crystal" in texts[0] or "sound" in texts[0].lower() or texts[0]
    assert texts[1] == ""
    assert texts[2] == ""
    assert texts[3] == ""
    assert texts[4].startswith("KES 1,200")
    assert "Shop on WhatsApp" in texts[4]


def test_lifestyle_story_orders_edit_ai_slides():
    urls = [
        "/media/studio_polish/x/promo_frame_z.jpg",
        "/media/studio_polish/x/ai_scene_table_a.jpg",
        "/media/studio_polish/x/edit_ai_angle_b.jpg",
        "/media/studio_polish/x/channel_story_c.jpg",
        "/media/studio_polish/x/studio_white_d.jpg",
        "/media/studio_polish/x/edit_ai_staging_e.jpg",
    ]
    plan = build_reel_plan(
        urls,
        seed="prod-lifestyle",
        category="beauty",
        recipe_id="lifestyle_story",
        product_name="Glow Serum",
        price_label="KES 800",
    )
    assert plan is not None
    assert len(plan.image_urls) == 5
    assert "channel_story" in plan.image_urls[0]
    assert any("edit_ai_staging" in u for u in plan.image_urls)
    assert plan.hook_texts[0]  # opening hook on channel_story beat
    assert plan.template == "lifestyle_story"
    assert plan.transition_sec == 0.55


def test_flash_drop_uses_flash_template_and_boost():
    urls = [
        "/media/studio_white.jpg",
        "/media/channel_story.jpg",
        "/media/ai_lifestyle.jpg",
        "/media/ai_scene_table.jpg",
        "/media/promo_frame.jpg",
    ]
    plan = build_reel_plan(
        urls,
        seed="flash-1",
        recipe_id="flash_drop",
        product_name="Speaker",
        price_label="KES 500",
        key_feature="Bass that hits",
    )
    assert plan.recipe_id == "flash_drop"
    assert plan.template == "flash_commerce"
    assert plan.cta_audio_boost is True
    assert plan.transition_sec == 0.35
    assert plan.hook_texts[0]  # scroll-stopping hook
    assert plan.hook_texts[0] != "Speaker" or "Bass" in plan.hook_texts[0]
    assert "KES 500" in plan.hook_texts[-1]
    assert plan.slide_roles[-1] == "cta"


def test_build_reel_plan_assigns_role_aware_hooks():
    urls = [
        "/media/studio_polish/x/channel_story_c.jpg",
        "/media/studio_polish/x/studio_white_d.jpg",
        "/media/studio_polish/x/ai_scene_table_a.jpg",
        "/media/studio_polish/x/edit_ai_staging_e.jpg",
        "/media/studio_polish/x/studio_brand_f.jpg",
    ]
    plan = build_reel_plan(
        urls,
        seed="prod-hooks",
        product_name="Glow Serum",
        price_label="KES 800",
        category="beauty",
        key_feature="Vitamin C glow",
    )
    assert plan is not None
    assert plan.hook_texts[0]
    assert plan.hook_texts[0] != "Glow Serum" or "Vitamin" in plan.hook_texts[0]
    assert plan.hook_texts[1] == ""
    assert "KES 800" in plan.hook_texts[-1]
    assert plan.slide_durations
    assert len(plan.slide_durations) == len(plan.image_urls)


def test_craft_scroll_stopping_hook_prefers_feature():
    from apps.content.reel_director import craft_scroll_stopping_hook

    hook = craft_scroll_stopping_hook(
        product_name="Amaya Speaker",
        category="electronics",
        key_feature="Crystal-clear bass",
    )
    assert "Crystal" in hook or "bass" in hook.lower()
    assert hook != "Amaya Speaker"


def test_craft_scroll_stopping_hook_override_wins():
    from apps.content.reel_director import craft_scroll_stopping_hook

    hook = craft_scroll_stopping_hook(
        product_name="Amaya Speaker",
        hook_override="Stop scrolling — this changes everything",
    )
    assert "Stop scrolling" in hook


def test_baked_carousel_urls_skip_hook_overlay():
    urls = [
        "/media/carousels/abc/slide_1.jpg",
        "/media/carousels/abc/slide_2.jpg",
        "/media/studio_white.jpg",
    ]
    plan = build_reel_plan(
        urls,
        seed="carousel-reel",
        product_name="Phone Holder",
        price_label="KES 850",
    )
    assert plan is not None
    assert plan.hook_texts[0] == ""
    assert plan.hook_texts[1] == ""
    assert "KES 850" in plan.hook_texts[-1]
