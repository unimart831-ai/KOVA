"""Tests for polished product → carousel/reel routing."""

import pytest

from apps.accounts.models import User
from apps.content.models import Post
from apps.content.product_visuals import (
    polished_carousel_sources,
    polished_reel_sources,
    product_has_polished_gallery,
    product_has_usable_gallery,
    refresh_product_polished_posts,
    try_apply_product_polished_media,
)
from apps.products.models import Product


@pytest.fixture
def user(db):
    return User.objects.create_user(username="pv", email="pv@kova.ai", password="x")


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Blue Kitenge Dress",
        price=2500,
        additional_images=[
            "/media/studio_polish/p1_studio_white.jpg",
            "/media/studio_polish/p1_edit_ai_angle_1.jpg",
            "/media/studio_polish/p1_ai_scene_table.jpg",
        ],
    )


def test_product_has_polished_gallery(product):
    assert product_has_polished_gallery(product) is True


def test_polished_carousel_sources_curates_studio_urls(product):
    urls = polished_carousel_sources(product)
    assert len(urls) >= 2
    assert all("studio" in u or "edit_ai" in u or "ai_scene" in u for u in urls)


def test_try_apply_skips_flux_for_carousel_with_product(user, product, monkeypatch):
    from apps.content.models import Post

    def _fake_carousel(post, prod, **kwargs):
        post.media_urls = [
            "https://cdn.example.com/s1.jpg",
            "https://cdn.example.com/s2.jpg",
        ]
        post.media_status = Post.MediaStatus.GENERATED
        post.save(update_fields=["media_urls", "media_status", "updated_at"])
        return post.media_urls

    monkeypatch.setattr(
        "apps.media.carousel_bridge.generate_branded_carousel_urls",
        _fake_carousel,
    )

    post = Post.objects.create(
        user=user,
        product=product,
        platform="instagram",
        content_text="Shop now",
        post_format=Post.PostFormat.CAROUSEL,
        carousel_slides=[{"heading": "Hook", "image_prompt": "should not run"}],
        media_status=Post.MediaStatus.NONE,
    )
    assert try_apply_product_polished_media(post) is True
    post.refresh_from_db()
    assert post.media_status == Post.MediaStatus.GENERATED
    assert len(post.media_urls or []) == 2


def test_refresh_product_polished_posts_fixes_failed_reel(user, product, monkeypatch):
    def _fake_reel(post, prod):
        from apps.content.models import Post as P

        post.media_urls = ["/media/studio_polish/p1_studio_white.jpg"]
        post.media_status = P.MediaStatus.GENERATED
        post.save(update_fields=["media_urls", "media_status", "updated_at"])
        return True

    monkeypatch.setattr(
        "apps.content.product_visuals.apply_polished_reel_post",
        _fake_reel,
    )

    post = Post.objects.create(
        user=user,
        product=product,
        platform="instagram",
        content_text="Reel",
        post_format=Post.PostFormat.REEL,
        media_status=Post.MediaStatus.FAILED,
    )
    assert refresh_product_polished_posts(product) == 1
    post.refresh_from_db()
    assert post.media_status == Post.MediaStatus.GENERATED


@pytest.fixture
def as_is_product(user):
    return Product.objects.create(
        user=user,
        name="Handmade Basket",
        price=1200,
        visual_mode=Product.VisualMode.AS_IS,
        additional_images=[
            "/media/product_images/basket_front.jpg",
            "/media/product_images/basket_side.jpg",
            "/media/product_images/basket_detail.jpg",
        ],
    )


def test_as_is_product_has_usable_gallery_not_polished(as_is_product):
    assert product_has_polished_gallery(as_is_product) is False
    assert product_has_usable_gallery(as_is_product) is True


def test_as_is_carousel_sources_preserve_upload_order(as_is_product):
    urls = polished_carousel_sources(as_is_product, max_images=5)
    assert len(urls) == 3
    assert all("product_images" in u for u in urls)
    assert urls[0] == "/media/product_images/basket_front.jpg"


def test_as_is_reel_sources_use_all_uploads(as_is_product):
    sources = polished_reel_sources(as_is_product)
    assert len(sources) == 3
    assert all("product_images" in u for u in sources)


def test_try_apply_skips_flux_for_as_is_reel(user, as_is_product, monkeypatch):
    queued = []

    def _fake_queue(post_id):
        queued.append(post_id)

    monkeypatch.setattr("apps.content.tasks._queue_reel_compose", _fake_queue)

    post = Post.objects.create(
        user=user,
        product=as_is_product,
        platform="instagram",
        content_text="Order now",
        post_format=Post.PostFormat.REEL,
        media_status=Post.MediaStatus.NONE,
    )
    assert try_apply_product_polished_media(post) is True
    post.refresh_from_db()
    assert post.media_status == Post.MediaStatus.GENERATED
    assert len(post.media_urls or []) == 3
    meta = post.visual_metadata or {}
    assert meta.get("prefer_photoroom_video") is False
    assert meta.get("reel_compose_backend") == "ffmpeg"
    assert queued == [str(post.pk)]
