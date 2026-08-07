"""Tests for public shop reels on commerce pages."""

import pytest
from django.urls import reverse

from apps.create.content.models import Post
from apps.commerce.products.commerce_reels import get_public_product_reel, get_public_shop_reels
from apps.commerce.products.models import Product


def _ready_reel(user, product, *, video_url="https://cdn.example.com/reel.mp4"):
    return Post.objects.create(
        user=user,
        product=product,
        content_text=f"Reel for {product.name}",
        post_format=Post.PostFormat.REEL,
        status=Post.Status.APPROVED,
        visual_metadata={
            "reel_video_url": video_url,
            "reel_thumbnail_url": "https://cdn.example.com/thumb.jpg",
            "video_compose_status": "completed",
        },
    )


@pytest.mark.django_db
class TestCommerceReels:
    def test_get_public_shop_reels_filters_draft_and_dedupes_products(self, user):
        user.profile.page_slug = "reel-shop"
        user.profile.save()
        product_a = Product.objects.create(
            user=user,
            name="Lotion",
            commerce_slug="lotion",
            price=350,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        product_b = Product.objects.create(
            user=user,
            name="Comb",
            commerce_slug="comb",
            price=120,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        _ready_reel(user, product_a)
        _ready_reel(user, product_a)  # newer duplicate for same product
        _ready_reel(user, product_b)
        Post.objects.create(
            user=user,
            product=product_a,
            content_text="Draft reel",
            post_format=Post.PostFormat.REEL,
            status=Post.Status.DRAFT,
            visual_metadata={"reel_video_url": "https://cdn.example.com/draft.mp4"},
        )

        reels = get_public_shop_reels(user.profile)
        assert len(reels) == 2
        slugs = {r["commerce_slug"] for r in reels}
        assert slugs == {"lotion", "comb"}

    def test_pending_approval_reels_show_on_shop(self, user):
        user.profile.page_slug = "reel-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Pending Reel Item",
            commerce_slug="pending-reel",
            price=500,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        Post.objects.create(
            user=user,
            product=product,
            content_text="Pending reel",
            post_format=Post.PostFormat.REEL,
            status=Post.Status.PENDING_APPROVAL,
            visual_metadata={
                "reel_video_url": "https://cdn.example.com/pending.mp4",
            },
        )
        reels = get_public_shop_reels(user.profile)
        assert len(reels) == 1
        assert reels[0]["video_url"] == "https://cdn.example.com/pending.mp4"

    def test_get_public_product_reel_returns_latest_ready(self, user):
        product = Product.objects.create(
            user=user,
            name="Widget",
            commerce_slug="widget",
            price=500,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        old = _ready_reel(user, product, video_url="https://cdn.example.com/old.mp4")
        new = _ready_reel(user, product, video_url="https://cdn.example.com/new.mp4")
        from datetime import timedelta
        from django.utils import timezone

        Post.objects.filter(pk=new.pk).update(
            created_at=old.created_at + timedelta(seconds=1),
        )
        new.refresh_from_db()
        assert new.created_at > old.created_at

        reel = get_public_product_reel(product)
        assert reel is not None
        assert reel["video_url"] == "https://cdn.example.com/new.mp4"

    def test_shop_index_renders_reel_strip(self, client, user):
        user.profile.page_slug = "reel-shop"
        user.profile.company_name = "Reel Shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Featured Item",
            commerce_slug="featured-item",
            price=999,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        _ready_reel(user, product)

        response = client.get(reverse("public_shop", kwargs={"page_slug": "reel-shop"}))
        content = response.content.decode()
        assert response.status_code == 200
        assert "Shop reels" in content
        assert "shop-hero-carousel" in content
        assert "reel-video" in content
        assert "muted autoplay loop playsinline" in content
        assert "https://cdn.example.com/reel.mp4" in content

    def test_product_page_renders_featured_reel(self, client, user):
        user.profile.page_slug = "reel-shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Featured Item",
            commerce_slug="featured-item",
            price=999,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        _ready_reel(user, product)

        response = client.get(
            reverse(
                "public_commerce",
                kwargs={"page_slug": "reel-shop", "commerce_slug": "featured-item"},
            )
        )
        content = response.content.decode()
        assert response.status_code == 200
        assert "See it in action" in content
        assert "product-reel-video" in content
        assert "reel-unmute-btn" in content
        reel_pos = content.find("product-reel-hero")
        gallery_pos = content.find("gallery-card")
        if reel_pos >= 0 and gallery_pos >= 0:
            assert reel_pos < gallery_pos
