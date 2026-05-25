"""Tests for primary image exclude toggle."""

from apps.products.models import Product


def test_all_image_urls_skips_excluded_primary(db):
    product = Product.objects.create(
        name="Test",
        exclude_primary_image=True,
        additional_images=["https://cdn.example.com/studio.jpg"],
    )
    product.image = "product_images/test.jpg"
    product.save()
    urls = product.all_image_urls
    assert len(urls) == 1
    assert urls[0] == "https://cdn.example.com/studio.jpg"


def test_cover_image_url_falls_back_to_plus_scene(db):
    product = Product.objects.create(
        name="Test",
        exclude_primary_image=True,
        additional_images=["https://cdn.example.com/hero.jpg"],
    )
    product.image = "product_images/original.jpg"
    product.save()
    assert product.cover_image_url == "https://cdn.example.com/hero.jpg"


def test_carousel_image_urls_excludes_channel(db):
    product = Product.objects.create(
        name="Test",
        additional_images=[
            "https://cdn.example.com/studio_white.jpg",
            "https://cdn.example.com/channel_story_abc.jpg",
        ],
    )
    assert len(product.carousel_image_urls) == 1
    assert "studio_white" in product.carousel_image_urls[0]


def test_shop_gallery_urls_excludes_promo_frame(db):
    product = Product.objects.create(
        name="Test",
        additional_images=[
            "https://cdn.example.com/studio_white.jpg",
            "https://cdn.example.com/promo_frame_abc.jpg",
            "https://cdn.example.com/ai_scene_table.jpg",
        ],
    )
    assert len(product.shop_gallery_urls) == 2
    assert not any("promo_frame" in u for u in product.shop_gallery_urls)


def test_all_image_urls_skips_non_string_entries(db):
    product = Product.objects.create(
        name="Test",
        additional_images=[
            "https://cdn.example.com/a.jpg",
            {"ignored": True},
            99,
            "https://cdn.example.com/b.jpg",
        ],
    )
    assert product.all_image_urls == [
        "https://cdn.example.com/a.jpg",
        "https://cdn.example.com/b.jpg",
    ]
