"""Tests for campaign-level bulk approval."""

import pytest

from apps.create.content.campaign_approval import (
    approve_campaign_posts,
    campaign_rollout_minutes,
    sync_campaign_after_approval,
)
from apps.create.content.campaigns import ensure_campaign_for_seed
from apps.create.content.models import ContentSeed, MarketingCampaign, Post
from apps.core.platforms.models import SocialAccount


@pytest.fixture
def ig_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        platform_user_id="ig-1",
        username="testig",
        is_active=True,
    )


@pytest.fixture
def fb_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="facebook",
        platform_user_id="fb-1",
        username="testfb",
        is_active=True,
    )


def _post(user, seed, account, fmt, role, *, needs_media=False):
    post = Post.objects.create(
        user=user,
        seed=seed,
        social_account=account,
        platform=account.platform,
        post_format=fmt,
        content_text=f"Test {role}",
        status=Post.Status.PENDING_APPROVAL,
        content_dna={"bundle_role": role},
    )
    if not needs_media and fmt in ("image", "carousel", "story", "reel"):
        post.media_urls = ["https://example.com/img.jpg"]
        post.media_status = Post.MediaStatus.UPLOADED
        post.save(update_fields=["media_urls", "media_status"])
    return post


@pytest.mark.django_db
class TestCampaignRolloutOrder:
    def test_reel_before_carousel(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Test")
        reel = _post(user, seed, ig_account, "reel", "ig_reel")
        carousel = _post(user, seed, ig_account, "carousel", "ig_carousel")
        assert campaign_rollout_minutes(reel) < campaign_rollout_minutes(carousel)


@pytest.mark.django_db
class TestApproveCampaignPosts:
    def test_approves_all_ready_posts(self, user, ig_account, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Campaign")
        ensure_campaign_for_seed(seed, title="Campaign")
        posts = [
            _post(user, seed, ig_account, "reel", "ig_reel"),
            _post(user, seed, ig_account, "image", "ig_feed"),
            _post(user, seed, fb_account, "text", "fb_feed"),
        ]
        result = approve_campaign_posts(user, posts, "next_best")
        assert result.approved_count == 3
        assert result.skipped_media == 0
        for p in posts:
            p.refresh_from_db()
            assert p.status == Post.Status.APPROVED
            assert p.scheduled_at is not None

    def test_staggered_rollout(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Stagger")
        reel = _post(user, seed, ig_account, "reel", "ig_reel")
        carousel = _post(user, seed, ig_account, "carousel", "ig_carousel")
        carousel.carousel_slides = [{"heading": "A", "body": "B", "image_url": "/x.jpg"}] * 6
        carousel.save(update_fields=["carousel_slides"])

        approve_campaign_posts(user, [reel, carousel], "next_best")
        reel.refresh_from_db()
        carousel.refresh_from_db()
        assert carousel.scheduled_at > reel.scheduled_at

    def test_skips_media_blocked(self, user, ig_account, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Blocked")
        blocked = _post(user, seed, ig_account, "image", "ig_feed", needs_media=True)
        ready = _post(user, seed, fb_account, "text", "fb_feed")

        result = approve_campaign_posts(user, [blocked, ready], "next_best")
        assert result.approved_count == 1
        assert result.skipped_media == 1
        blocked.refresh_from_db()
        assert blocked.status == Post.Status.PENDING_APPROVAL

    def test_marks_campaign_approved(self, user, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Sync")
        campaign = ensure_campaign_for_seed(seed, title="Sync")
        post = _post(user, seed, fb_account, "text", "fb_feed")

        approve_campaign_posts(user, [post], "next_best")
        sync_campaign_after_approval(campaign, seed)
        campaign.refresh_from_db()
        assert campaign.status == MarketingCampaign.Status.APPROVED


@pytest.mark.django_db
class TestCampaignApproveView:
    def test_campaign_approve_via_request_factory(self, user, fb_account):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        from apps.create.content.views.queue import _handle_campaign_approve

        seed = ContentSeed.objects.create(user=user, idea="View test")
        campaign = ensure_campaign_for_seed(seed, title="View test")
        post = _post(user, seed, fb_account, "text", "fb_feed")

        request = RequestFactory().post("/", {"schedule_intent": "next_best"})
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)

        response = _handle_campaign_approve(request, campaign=campaign)
        assert response.status_code == 302
        post.refresh_from_db()
        assert post.status == Post.Status.APPROVED
        campaign.refresh_from_db()
        assert campaign.status == MarketingCampaign.Status.APPROVED
