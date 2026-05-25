"""Tests for product copy enrichment."""

from apps.products.product_copy import (
    build_product_carousel_plan,
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
    assert out.count("\n\n") == 3
    assert "32-inch smart TV" in out


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
