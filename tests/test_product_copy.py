"""Tests for product copy enrichment."""

from apps.products.product_copy import (
    build_product_carousel_plan,
    description_sentence_count,
    format_feature_bullets,
    format_product_description,
    improve_product_name,
    should_improve_product_name,
)


class _Product:
    def __init__(self, name="Test", description="", price=1000, currency="KES"):
        self.name = name
        self.description = description
        self.price = price
        self.currency = currency
        self.additional_images = []
        self.image = None

    @property
    def display_price(self):
        return f"{self.currency} {self.price:,}" if self.price else ""

    @property
    def all_image_urls(self):
        return ["/media/a.jpg", "/media/b.jpg", "/media/c.jpg"]

    @property
    def carousel_image_urls(self):
        return self.all_image_urls


def test_improve_vague_tv_name():
    analysis = {
        "improved_name": 'Samsung 32" Full HD Smart LED TV',
        "detected_name": 'Samsung 32" Smart TV',
        "brand": "Samsung",
    }
    assert should_improve_product_name('32" TV', analysis) is True
    assert improve_product_name('32" TV', analysis) == 'Samsung 32" Full HD Smart LED TV'


def test_format_description_as_paragraphs():
    analysis = {
        "description_sentences": [
            "This is a 32-inch smart TV with crisp Full HD picture.",
            "Built-in streaming apps make binge-watching effortless.",
            "Perfect for bedrooms, kitchens, and small living spaces.",
            "Order today and upgrade your home entertainment.",
        ]
    }
    out = format_product_description("", analysis)
    assert out.count("\n\n") >= 2
    assert description_sentence_count(out) >= 3
    assert "32-inch smart TV" in out


def test_format_description_expands_short_ai_output():
    from apps.products.product_copy import description_sentence_count

    analysis = {
        "description_sentences": [
            "This is a VON 20L microwave for quick meals.",
            "It has a sleek design for modern kitchens.",
        ],
        "key_features": ["20L capacity", "Easy controls"],
        "target_audience": "busy families",
    }
    out = format_product_description("", analysis, product_name="VON Microwave")
    assert description_sentence_count(out) >= 3


def test_format_feature_bullets_varies_emojis():
    features = ["Magnetic Wireless Charging", "22.5W fast charge", "Compact travel size"]
    out = format_feature_bullets(features, seed="product-123", platform="instagram")
    lines = out.split("\n")
    assert len(lines) == 3
    emojis = [line.split(" ", 1)[0] for line in lines]
    assert len(set(emojis)) == 3
    assert "✅" not in emojis or emojis.count("✅") <= 1


def test_format_feature_bullets_differs_by_platform():
    features = ["Feature A", "Feature B", "Feature C"]
    ig = format_feature_bullets(features, seed="p1", platform="instagram")
    li = format_feature_bullets(features, seed="p1", platform="linkedin")
    assert ig.split("\n")[0] != li.split("\n")[0]


def test_strip_feature_bullet():
    from apps.products.product_copy import strip_feature_bullet

    assert strip_feature_bullet("✅ Fast charging") == "Fast charging"
    assert strip_feature_bullet("✓ Magnetic mount") == "Magnetic mount"


def test_clean_description_sentence_removes_labels():
    from apps.products.product_copy import clean_description_sentence, format_product_description

    assert clean_description_sentence(
        "Sentence 1: This is a VON microwave that provides effective cooking."
    ) == "This is a VON microwave that provides effective cooking."
    assert clean_description_sentence(
        "Sentence 4 (optional): Enhance your kitchen with this essential appliance."
    ) == "Enhance your kitchen with this essential appliance."

    raw = (
        "Sentence 1: This is a VON microwave.\n\n"
        "Sentence 2: With its sleek design, it stands out.\n\n"
        "Sentence 3: Perfect for busy families."
    )
    out = format_product_description(raw)
    assert "Sentence 1" not in out
    assert "Sentence 2" not in out
    assert "VON microwave" in out
    assert description_sentence_count(out) >= 3


def test_carousel_plan_includes_story_and_price():
    product = _Product(name='Samsung 32" Smart TV', price=43000)
    analysis = {
        "description_sentences": [
            "Bright Full HD panel for everyday viewing.",
            "Stream Netflix, YouTube, and more out of the box.",
            "Ideal for compact rooms and guest bedrooms.",
        ],
        "key_features": ["Full HD display", "Smart apps built-in", "Slim bezel design"],
        "campaign_angle": "Big screen entertainment without the big price",
    }
    plan = build_product_carousel_plan(product, analysis, analysis["key_features"])
    layouts = [s["layout"] for s in plan]
    assert layouts[0] == "hero_hook"
    assert "story_card" in layouts
    assert "price_reveal" in layouts
    assert len(plan) >= 4
    benefit_headlines = [s["headline"] for s in plan if s["layout"].startswith("benefit")]
    assert len({h.split(" ", 1)[0] for h in benefit_headlines}) >= 2
