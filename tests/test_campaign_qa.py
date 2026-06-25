"""Tests for campaign QA scoring and publish gate."""

import pytest
from django.test import override_settings

from apps.content.campaign_qa import (
    audit_campaign_qa,
    check_post_publish_gate,
    get_publish_min_score,
    refresh_campaign_qa,
    score_post_qa,
)
from apps.content.campaigns import ensure_campaign_for_seed
from apps.content.models import ContentSeed, Post
from apps.platforms.models import SocialAccount


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


def _good_post(user, seed, account, **kwargs):
    defaults = {
        "user": user,
        "seed": seed,
        "social_account": account,
        "platform": account.platform,
        "post_format": "image",
        "content_text": (
            "Save this for your weekend glow-up ✨ Our bestselling handbags are back — "
            "premium quality, limited stock. Shop via link in bio."
        ),
        "status": Post.Status.PENDING_APPROVAL,
        "cta_url": "https://example.com/c/sale/",
        "cta_type": "link",
        "utm_campaign": "weekend-sale",
        "first_comment": "Shop now — link in bio",
        "media_urls": ["https://example.com/img.jpg"],
        "media_status": Post.MediaStatus.UPLOADED,
        "content_dna": {"blueprint_quality": 85},
        "ai_angle": "Urgency + scarcity",
        "ai_framework": "Hook → Value → CTA",
    }
    defaults.update(kwargs)
    return Post.objects.create(**defaults)


@pytest.mark.django_db
class TestPublishMinScore:
    @override_settings(CAMPAIGN_PUBLISH_MIN_QUALITY=75)
    def test_default_threshold(self, user):
        assert get_publish_min_score(user) == 75

    @override_settings(CAMPAIGN_PUBLISH_MIN_QUALITY=80)
    def test_settings_override(self, user):
        assert get_publish_min_score(user) == 80


@pytest.mark.django_db
class TestScorePostQA:
    def test_high_quality_post(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Sale")
        post = _good_post(user, seed, ig_account)
        result = score_post_qa(post, seed=seed)
        assert result.overall >= 75
        assert result.dimensions["cta"] >= 70

    def test_low_quality_missing_cta_and_media(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Weak")
        post = Post.objects.create(
            user=user,
            seed=seed,
            social_account=ig_account,
            platform="instagram",
            post_format="image",
            content_text="Hi",
            status=Post.Status.PENDING_APPROVAL,
        )
        result = score_post_qa(post, seed=seed)
        assert result.overall < 75
        assert result.issues


@pytest.mark.django_db
class TestCampaignQAAudit:
    def test_publish_ready_campaign(self, user, ig_account, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Strong campaign")
        campaign = ensure_campaign_for_seed(seed, title="Strong campaign")
        posts = [
            _good_post(user, seed, ig_account),
            _good_post(
                user, seed, fb_account,
                post_format="text",
                content_text=(
                    "Our weekend handbag sale is live. Premium leather, "
                    "Kenyan craftsmanship. Order on WhatsApp or visit our shop."
                ),
            ),
        ]
        report = audit_campaign_qa(campaign, posts, user)
        assert report.overall >= 75
        assert report.publish_ready is True
        assert len(report.dimensions) == 6

    def test_blocked_below_threshold(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Weak")
        campaign = ensure_campaign_for_seed(seed, title="Weak")
        post = Post.objects.create(
            user=user,
            seed=seed,
            social_account=ig_account,
            platform="instagram",
            post_format="image",
            content_text="Buy now",
            status=Post.Status.PENDING_APPROVAL,
        )
        report = audit_campaign_qa(campaign, [post], user)
        assert report.publish_ready is False
        assert "campaign_score" in report.gates_failed

    def test_refresh_persists_on_campaign(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Persist")
        campaign = ensure_campaign_for_seed(seed, title="Persist")
        post = _good_post(user, seed, ig_account)
        report = refresh_campaign_qa(campaign, posts=[post], user=user)
        campaign.refresh_from_db()
        assert campaign.quality_score == report.overall
        assert "qa_report" in campaign.proposal_meta
        post.refresh_from_db()
        assert post.content_dna.get("qa_score") == report.posts[0].overall


@pytest.mark.django_db
class TestPublishGate:
    @override_settings(CAMPAIGN_PUBLISH_MIN_QUALITY=75)
    def test_blocks_low_quality(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Gate test")
        ensure_campaign_for_seed(seed, title="Gate test")
        post = Post.objects.create(
            user=user,
            seed=seed,
            social_account=ig_account,
            platform="instagram",
            post_format="image",
            content_text="Short",
            status=Post.Status.APPROVED,
        )
        allowed, reason, score = check_post_publish_gate(post, user)
        assert allowed is False
        assert reason
        assert score < 75

    @override_settings(CAMPAIGN_PUBLISH_MIN_QUALITY=75)
    def test_allows_quality_campaign(self, user, ig_account):
        seed = ContentSeed.objects.create(user=user, idea="Good gate")
        ensure_campaign_for_seed(seed, title="Good gate")
        post = _good_post(user, seed, ig_account, status=Post.Status.APPROVED)
        allowed, reason, score = check_post_publish_gate(post, user)
        assert allowed is True
        assert score >= 75
