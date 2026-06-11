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


def test_hook_texts_price_only_on_last_frame():
    texts = build_hook_texts(
        slide_count=5,
        slide_roles=["hook", "hero", "desire", "desire", "cta"],
        product_name="Amaya Speaker",
        price_label="KES 1,200",
    )
    assert texts[0] == "Amaya Speaker"
    assert texts[1] == ""
    assert texts[-1] == "KES 1,200\nOrder on WhatsApp"
    assert "Shop" not in texts[-1]


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
    assert plan.hook_texts[-1].startswith("KES 800")
    assert "Order on WhatsApp" in plan.hook_texts[-1]
    assert plan.template == "story_arc"


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
    )
    assert plan.recipe_id == "flash_drop"
    assert plan.template == "flash_commerce"
    assert plan.cta_audio_boost is True
    assert plan.transition_sec == 0.35
