"""
Tests for content creation flow: seeds, posts, scheduling.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.accounts.models import User, UserProfile
from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount


@pytest.fixture
def social_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="twitter",
        platform_user_id="12345",
        username="testhandle",
        is_active=True,
    )


@pytest.fixture
def seed(user):
    return ContentSeed.objects.create(
        user=user,
        idea="Test idea for AI content",
        status=ContentSeed.SeedStatus.NEW,
    )


@pytest.mark.django_db
class TestContentSeed:
    def test_create_seed(self, user):
        seed = ContentSeed.objects.create(user=user, idea="My brilliant content idea")
        assert seed.status == "new"
        assert str(seed).startswith("Seed:")

    def test_seed_ordering(self, user):
        s1 = ContentSeed.objects.create(user=user, idea="First")
        s2 = ContentSeed.objects.create(user=user, idea="Second")
        seeds = list(ContentSeed.objects.filter(user=user))
        assert seeds[0].pk == s2.pk  # most recent first


@pytest.mark.django_db
class TestPost:
    def test_create_post(self, user, social_account, seed):
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            seed=seed,
            content_text="Hello world from Kova!",
            status=Post.Status.DRAFT,
        )
        assert post.pk is not None
        assert post.status == "draft"

    def test_post_soft_delete(self, user, social_account):
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            content_text="Will be deleted",
        )
        post.soft_delete()
        assert Post.objects.filter(pk=post.pk).count() == 0
        assert Post.all_objects.filter(pk=post.pk).count() == 1

    def test_scheduling(self, user, social_account):
        future = timezone.now() + timezone.timedelta(hours=2)
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            content_text="Scheduled post",
            status=Post.Status.SCHEDULED,
            scheduled_at=future,
        )
        assert post.scheduled_at > timezone.now()

    def test_media_status_default(self, user, social_account):
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            content_text="No media",
        )
        assert post.media_status == Post.MediaStatus.NONE

    def test_edit_distance_tracking(self, user, social_account):
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            content_text="Edited text",
            ai_original_text="Original AI text",
            user_edited=True,
            edit_distance_ratio=0.35,
        )
        assert post.user_edited is True
        assert post.edit_distance_ratio == 0.35


@pytest.mark.django_db
class TestContentStudioView:
    def test_studio_requires_login(self, client):
        resp = client.get("/content/")
        assert resp.status_code == 302
        assert "login" in resp.url or "account" in resp.url

    def test_studio_loads_for_auth_user(self, auth_client):
        resp = auth_client.get("/content/")
        assert resp.status_code == 200

    def test_submit_seed_post(self, auth_client, user):
        """POST to submit_seed should create a ContentSeed."""
        SocialAccount.objects.create(
            user=user,
            platform="twitter",
            platform_user_id="99",
            username="u",
            is_active=True,
        )
        resp = auth_client.post("/content/submit-seed/", {
            "idea": "Test idea from pytest",
        })
        # Should redirect or return HTMX partial
        assert resp.status_code in (200, 302)
        assert ContentSeed.objects.filter(user=user, idea="Test idea from pytest").exists()


@pytest.mark.django_db
class TestRescheduleRateLimited:
    def test_reschedules_failed_rate_limited_post(self, auth_client, user, social_account):
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            content_text="Rate limited post",
            status=Post.Status.FAILED,
            publish_error="Twitter API rate limit exceeded (429)",
        )
        before = timezone.now()
        url = reverse("content:reschedule_rate_limited", kwargs={"post_id": post.id})
        resp = auth_client.post(url)
        assert resp.status_code == 302
        post.refresh_from_db()
        assert post.status == Post.Status.SCHEDULED
        assert post.publish_error == ""
        assert post.scheduled_at >= before + timezone.timedelta(minutes=29)

    def test_rejects_non_rate_limited_failure(self, auth_client, user, social_account):
        post = Post.objects.create(
            user=user,
            social_account=social_account,
            content_text="Other failure",
            status=Post.Status.FAILED,
            publish_error="Invalid media format",
        )
        url = reverse("content:reschedule_rate_limited", kwargs={"post_id": post.id})
        resp = auth_client.post(url)
        assert resp.status_code == 400
        post.refresh_from_db()
        assert post.status == Post.Status.FAILED
