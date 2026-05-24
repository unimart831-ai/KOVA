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
