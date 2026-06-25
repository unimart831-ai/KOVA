"""Professional carousel studio — curation, planning, image assignment."""

from apps.content.carousel_studio import (
    assign_images_to_plan,
    build_professional_carousel_plan,
    curate_carousel_images,
    prepare_carousel_generation,
)


class _Product:
    def __init__(self, name="Glow Serum", price=800, pk="p1"):
        self.name = name
        self.pk = pk
        self.display_price = f"KES {price:,}"
        self.carousel_image_urls = []
        self.all_image_urls = []


def test_curate_carousel_orders_composition_first():
    urls = [
        "/media/studio_polish/x/ai_scene_table.jpg",
        "/media/studio_polish/x/composition_hero.jpg",
        "/media/studio_polish/x/studio_white.jpg",
        "/media/studio_polish/x/channel_story.jpg",
    ]
    out = curate_carousel_images(urls)
    assert out[0].endswith("composition_hero.jpg")
    assert not any("channel_story" in u for u in out)


def test_professional_plan_product_first_layouts():
    product = _Product()
    analysis = {
        "description_sentences": ["Bright serum for daily glow."],
        "key_features": ["Vitamin C blend", "Lightweight texture"],
        "campaign_angle": "Radiant skin in one swipe",
    }
    plan = build_professional_carousel_plan(
        product, analysis, analysis["key_features"], image_count=4,
    )
    layouts = [s["layout"] for s in plan]
    assert layouts[0] == "clean_split"
    assert "minimal_caption" in layouts
    assert layouts[-1] == "price_bar"
    assert plan[0]["role"] == "hook"
    assert all("✨" not in s.get("headline", "") for s in plan)


def test_assign_images_unique_per_slide():
    urls = [
        "/media/studio_white_a.jpg",
        "/media/ai_scene_b.jpg",
        "/media/edit_ai_staging_c.jpg",
        "/media/studio_brand_d.jpg",
    ]
    plan = [
        {"layout": "clean_split", "image_index": 0},
        {"layout": "minimal_caption", "image_index": 1},
        {"layout": "side_panel", "image_index": 2},
    ]
    assigned = assign_images_to_plan(plan, urls)
    image_urls = [s["image_url"] for s in assigned]
    assert len(set(image_urls)) == len(image_urls)


def test_prepare_carousel_generation_binds_urls():
    product = _Product()
    product.carousel_image_urls = [
        "/media/studio_polish/x/studio_white.jpg",
        "/media/studio_polish/x/ai_lifestyle.jpg",
        "/media/studio_polish/x/edit_ai_angle.jpg",
    ]
    analysis = {
        "key_features": ["Fast absorbing"],
        "campaign_angle": "Daily glow",
        "description_sentences": ["Serum for bright skin."],
    }
    prepared = prepare_carousel_generation(product, analysis, analysis["key_features"])
    assert prepared.plan
    assert all(s.get("image_url") for s in prepared.plan)
