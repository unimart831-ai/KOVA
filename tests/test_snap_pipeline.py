"""Tests for Snap to Sell pipeline status API."""

import pytest
from django.urls import reverse

from apps.content.models import ContentSeed, Post
from apps.platforms.models import SocialAccount
from apps.products.models import Product
from apps.products.snap_pipeline import build_snap_pipeline_status


@pytest.fixture
def ig_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        platform_user_id="ig123",
        username="testig",
        is_active=True,
    )


@pytest.mark.django_db
class TestSnapPipelineStatus:
    def test_single_photo_skips_carousel_and_reel(self, user, ig_account):
        product = Product.objects.create(
            user=user,
            name="Solo item",
            source=Product.Source.SNAP,
        )
        data = build_snap_pipeline_status(product, user)
        assert data["photo_count"] == 0
        carousel = next(s for s in data["steps"] if s["id"] == "carousel")
        reel = next(s for s in data["steps"] if s["id"] == "reel")
        assert carousel["status"] == "skipped"
        assert reel["status"] == "skipped"

    def test_analyzing_when_no_seed_yet(self, user, ig_account):
        product = Product.objects.create(
            user=user,
            name="Fresh snap",
            source=Product.Source.SNAP,
        )
        data = build_snap_pipeline_status(product, user)
        analyze = next(s for s in data["steps"] if s["id"] == "analyze")
        assert analyze["status"] == "running"
        assert data["status"] == "processing"

    def test_completed_when_seed_done_no_carousel(self, user, ig_account):
        product = Product.objects.create(
            user=user,
            name="One photo product",
            source=Product.Source.SNAP,
        )
        seed = ContentSeed.objects.create(
            user=user,
            product=product,
            idea="Promote item",
            status=ContentSeed.SeedStatus.COMPLETED,
        )
        Post.objects.create(
            user=user,
            product=product,
            seed=seed,
            social_account=ig_account,
            platform="instagram",
            content_text="Buy now",
            status=Post.Status.PENDING_APPROVAL,
            media_status="generated",
        )
        data = build_snap_pipeline_status(product, user)
        assert data["status"] == "completed"
        assert data["terminal"] is True
        writing = next(s for s in data["steps"] if s["id"] == "writing")
        assert writing["status"] == "completed"

    def test_snap_status_endpoint(self, client, user, ig_account):
        client.force_login(user)
        product = Product.objects.create(
            user=user,
            name="API test",
            source=Product.Source.SNAP,
        )
        url = reverse("products:snap_status", kwargs={"product_id": product.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["product_id"] == str(product.pk)
        assert "steps" in payload
        assert payload["status"] == "processing"
