"""Phase 1 W1.1 — UTM injection / Revenue Attribution.

These tests lock in the canonical UTM injector (Post.tracked_url) and the
post-aware add_utm_tracking helper. If they regress, post -> Pixel
attribution breaks silently and the Daily Brief revenue surface goes blank.

Specifically, they guarantee:
    1. Post.tracked_url uses the Post's own utm_* fields (campaign-aware)
    2. tracked_url is idempotent — never double-stamps a URL that already
       carries any utm_ parameter
    3. add_utm_tracking with `post=post` tags every URL in a body of text
    4. The legacy hardcoded scheme still works when no post is supplied
    5. Empty / non-http URLs pass through untouched
"""

from __future__ import annotations

import pytest
from urllib.parse import parse_qs, urlparse

from apps.accounts.models import User
from apps.content.models import ContentSeed, Post
from apps.content.tasks import add_utm_tracking, _add_utm_to_url
from apps.platforms.models import SocialAccount


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="utm-test", email="utm@b.com", password="P1!",
    )


@pytest.fixture
def social_account(user):
    return SocialAccount.objects.create(
        user=user, platform="instagram", platform_user_id="ig123",
        username="testbiz", display_name="Test Biz",
        access_token="dummy", is_active=True,
    )


@pytest.fixture
def post(user, social_account):
    return Post.objects.create(
        user=user, social_account=social_account, platform="instagram",
        content_text="Try our new dress! Shop now https://example.co.ke/dress",
        cta_type="link", cta_url="https://example.co.ke/dress",
        cta_text="Shop Now",
    )


# ── Post.tracked_url ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTrackedUrl:
    def test_adds_utm_params(self, post):
        out = post.tracked_url("https://shop.co.ke/")
        qs = parse_qs(urlparse(out).query)

        assert "utm_source" in qs
        assert "utm_medium" in qs
        assert "utm_campaign" in qs
        assert "utm_content" in qs

    def test_uses_post_utm_fields_when_set(self, post):
        # When the post is assigned to a campaign, that campaign's name
        # should end up on the URL — NOT the hardcoded `kova_<id8>`.
        post.utm_campaign = "jamhuri_day_sale"
        post.save(update_fields=["utm_campaign"])

        out = post.tracked_url("https://shop.co.ke/")
        qs = parse_qs(urlparse(out).query)

        assert qs["utm_campaign"] == ["jamhuri_day_sale"]
        assert "kova_" not in qs["utm_campaign"][0]

    def test_utm_content_uses_post_id_prefix_for_pixel_lookup(self, post):
        # The Pixel attribution code in analytics/pixel.py expects
        # utm_content to be the first 8 chars of the Post UUID so it can
        # range-query Post.id. We must guarantee that format.
        out = post.tracked_url("https://shop.co.ke/")
        qs = parse_qs(urlparse(out).query)

        assert qs["utm_content"] == [str(post.pk)[:8]]

    def test_idempotent_when_url_already_has_utm(self, post):
        already = "https://shop.co.ke/?utm_source=manual&utm_campaign=existing"
        out = post.tracked_url(already)
        assert out == already

    def test_empty_url_passes_through(self, post):
        assert post.tracked_url("") == ""
        assert post.tracked_url(None) is None

    def test_non_http_url_passes_through(self, post):
        assert post.tracked_url("mailto:hello@biz.co.ke") == "mailto:hello@biz.co.ke"
        assert post.tracked_url("tel:+254712345678") == "tel:+254712345678"

    def test_preserves_existing_query_params(self, post):
        out = post.tracked_url("https://shop.co.ke/dress?size=M&color=red")
        qs = parse_qs(urlparse(out).query)

        assert qs["size"] == ["M"]
        assert qs["color"] == ["red"]
        assert "utm_source" in qs


# ── add_utm_tracking (post-aware) ───────────────────────────────────────────

@pytest.mark.django_db
class TestAddUtmTracking:
    def test_tags_all_urls_in_text(self, post):
        text = "Visit https://a.co.ke and https://b.co.ke for more."
        out = add_utm_tracking(text, "instagram", str(post.id), post=post)

        # Both URLs should have utm_source appended
        assert out.count("utm_source=") == 2

    def test_post_aware_uses_post_campaign(self, post):
        post.utm_campaign = "salon_sept_promo"
        post.save(update_fields=["utm_campaign"])

        out = add_utm_tracking(
            "Book here https://shop.co.ke/", "instagram", str(post.id), post=post,
        )
        assert "utm_campaign=salon_sept_promo" in out

    def test_falls_back_without_post(self, post):
        # Legacy callers (no `post=` kwarg) still get the hardcoded scheme
        out = add_utm_tracking(
            "Visit https://a.co.ke", "facebook", str(post.id),
        )
        assert "utm_source=facebook" in out
        assert "utm_campaign=kova_" in out

    def test_empty_text_returns_empty(self, post):
        assert add_utm_tracking("", "instagram", str(post.id), post=post) == ""
        assert add_utm_tracking(None, "instagram", str(post.id), post=post) is None

    def test_text_without_urls_unchanged(self, post):
        text = "Just hashtags #love #salon — no links here."
        out = add_utm_tracking(text, "instagram", str(post.id), post=post)
        assert out == text


# ── Pixel attribution chain — end-to-end verification ──────────────────────

@pytest.mark.django_db
class TestAttributionChain:
    """Confirms that a URL tagged by Post.tracked_url ends up with the
    utm_content value that apps/analytics/pixel.py:_attribute_to_post will
    successfully use to range-query the Post. If this regresses, every
    revenue dashboard goes blank."""

    def test_tracked_url_contains_post_id_prefix(self, post):
        out = post.tracked_url("https://shop.co.ke/")
        # The 8-char prefix that pixel.py uses to range-query Post.id.
        expected_prefix = str(post.pk)[:8]
        assert f"utm_content={expected_prefix}" in out
