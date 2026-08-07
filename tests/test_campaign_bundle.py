"""Tests for campaign bundle spec — audit, funnel carousel, and gap filling."""

import pytest

from apps.create.content.campaign_bundle import (
    audit_campaign_bundle,
    build_funnel_carousel_slides,
    ensure_campaign_bundle,
    required_bundle_roles,
)
from apps.create.content.campaigns import ensure_campaign_for_seed
from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount
from apps.commerce.products.models import Product


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Test Handbag",
        price=2500,
        currency="KES",
        is_active=True,
        commerce_slug="test-handbag",
    )


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


@pytest.mark.django_db
class TestRequiredBundleRoles:
    def test_instagram_facebook_bundle(self):
        roles = required_bundle_roles({"instagram", "facebook"})
        assert "ig_feed" in roles
        assert "ig_carousel" in roles
        assert "ig_story_1" in roles
        assert "fb_feed" in roles
        assert "ig_reel" in roles
        assert "fb_reel" in roles

    def test_linkedin_tiktok_when_connected(self):
        roles = required_bundle_roles({"linkedin", "tiktok"})
        assert "linkedin_copy" in roles
        assert "tiktok_copy" in roles
        assert "ig_reel" not in roles
        assert "fb_reel" not in roles

    def test_facebook_includes_carousel(self):
        roles = required_bundle_roles({"facebook"})
        assert "fb_feed" in roles
        assert "fb_carousel" in roles
        assert "fb_reel" in roles

    def test_content_types_filter_reels_only(self):
        roles = required_bundle_roles(
            {"instagram", "facebook"},
            content_types={"reels"},
        )
        assert "ig_reel" in roles
        assert "fb_reel" in roles
        assert "ig_carousel" not in roles
        assert "fb_carousel" not in roles
        assert "ig_feed" not in roles

    def test_content_types_filter_carousels_and_text(self):
        roles = required_bundle_roles(
            {"instagram", "facebook"},
            content_types={"carousels", "text"},
        )
        assert "ig_carousel" in roles
        assert "fb_carousel" in roles
        assert "fb_feed" in roles
        assert "ig_reel" not in roles
        assert "fb_reel" not in roles


@pytest.mark.django_db
class TestFunnelCarousel:
    def test_builds_six_slides(self, user, product):
        seed = ContentSeed.objects.create(
            user=user,
            idea="Weekend handbag flash sale",
            product=product,
        )
        slides = build_funnel_carousel_slides(seed)
        assert len(slides) == 6
        assert slides[0].get("funnel_role") == "hook"
        assert slides[-1].get("funnel_role") == "cta"
        for slide in slides:
            assert slide.get("heading")
            assert slide.get("body")
            assert slide.get("image_prompt")


@pytest.mark.django_db
class TestAuditCampaignBundle:
    def test_detects_missing_slots(self, user, ig_account, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Sale post")
        ensure_campaign_for_seed(seed, title="Sale post")
        posts = [
            Post.objects.create(
                user=user,
                seed=seed,
                social_account=ig_account,
                platform="instagram",
                post_format=Post.PostFormat.IMAGE,
                content_text="IG hero",
                media_urls=["https://example.com/a.jpg"],
                media_status=Post.MediaStatus.UPLOADED,
            ),
        ]
        audit = audit_campaign_bundle(posts, {"instagram", "facebook"})
        assert audit["total_count"] > 1
        assert not audit["complete"]
        assert audit["slots"]["ig_carousel"]["status"] == "missing"
        assert audit["slots"]["fb_feed"]["status"] == "missing"

    def test_complete_when_all_slots_filled(self, user, ig_account, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Full campaign")
        ensure_campaign_for_seed(seed, title="Full campaign")
        carousel_slides = build_funnel_carousel_slides(seed)

        posts = [
            Post.objects.create(
                user=user, seed=seed, social_account=ig_account, platform="instagram",
                post_format=Post.PostFormat.IMAGE, content_text="Feed",
                media_urls=["/m/a.jpg"], media_status=Post.MediaStatus.UPLOADED,
                content_dna={"bundle_role": "ig_feed"},
            ),
            Post.objects.create(
                user=user, seed=seed, social_account=ig_account, platform="instagram",
                post_format=Post.PostFormat.CAROUSEL, content_text="Swipe",
                carousel_slides=carousel_slides,
                media_urls=["/m/1.jpg"] * 6, media_status=Post.MediaStatus.GENERATED,
                content_dna={"bundle_role": "ig_carousel"},
            ),
        ]
        for i in range(1, 4):
            posts.append(Post.objects.create(
                user=user, seed=seed, social_account=ig_account, platform="instagram",
                post_format=Post.PostFormat.STORY, content_text=f"Story {i}",
                media_urls=[f"/m/s{i}.jpg"], media_status=Post.MediaStatus.GENERATED,
                content_dna={"bundle_role": f"ig_story_{i}"},
            ))
        posts.append(Post.objects.create(
            user=user, seed=seed, social_account=ig_account, platform="instagram",
            post_format=Post.PostFormat.REEL, content_text="Reel hook",
            media_urls=["/m/r.jpg"], media_status=Post.MediaStatus.GENERATED,
            content_dna={"bundle_role": "ig_reel"},
        ))
        posts.append(Post.objects.create(
            user=user, seed=seed, social_account=fb_account, platform="facebook",
            post_format=Post.PostFormat.REEL, content_text="FB reel hook",
            media_urls=["/m/fr.jpg"], media_status=Post.MediaStatus.GENERATED,
            content_dna={"bundle_role": "fb_reel"},
        ))
        posts.append(Post.objects.create(
            user=user, seed=seed, social_account=fb_account, platform="facebook",
            post_format=Post.PostFormat.TEXT, content_text="FB post",
            content_dna={"bundle_role": "fb_feed"},
        ))
        posts.append(Post.objects.create(
            user=user, seed=seed, social_account=fb_account, platform="facebook",
            post_format=Post.PostFormat.CAROUSEL, content_text="FB carousel",
            carousel_slides=carousel_slides,
            media_urls=["/m/1.jpg"] * 6, media_status=Post.MediaStatus.GENERATED,
            content_dna={"bundle_role": "fb_carousel"},
        ))

        audit = audit_campaign_bundle(posts, {"instagram", "facebook"})
        assert audit["complete"]
        assert audit["ready_count"] == audit["total_count"]


@pytest.mark.django_db
class TestEnsureCampaignBundle:
    def test_fills_missing_deliverables(self, user, ig_account, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Bundle fill test")
        ensure_campaign_for_seed(seed, title="Bundle fill test")
        source = Post.objects.create(
            user=user,
            seed=seed,
            social_account=fb_account,
            platform="facebook",
            post_format=Post.PostFormat.TEXT,
            content_text="Original Facebook angle for the weekend sale.",
        )
        account_map = {"instagram": ig_account, "facebook": fb_account}
        created = ensure_campaign_bundle(
            seed,
            user,
            [source],
            account_map=account_map,
            initial_status=Post.Status.PENDING_APPROVAL,
        )
        assert len(created) >= 6  # carousel, 3 stories, ig reel, fb reel, ig feed at minimum

        all_posts = list(Post.objects.filter(seed=seed))
        audit = audit_campaign_bundle(all_posts, {"instagram", "facebook"})
        assert audit["slots"]["ig_carousel"]["status"] != "missing"
        assert audit["slots"]["ig_reel"]["status"] != "missing"
        assert audit["slots"]["fb_reel"]["status"] != "missing"
        assert audit["slots"]["ig_feed"]["status"] != "missing"

        campaign = seed.marketing_campaign
        campaign.refresh_from_db()
        assert "bundle_audit" in (campaign.proposal_meta or {})
        assert campaign.proposal_meta["bundle_audit"]["total_count"] > 0
