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

from apps.core.accounts.models import User
from apps.create.content.models import ContentSeed, Post
from apps.create.content.tasks import add_utm_tracking, _add_utm_to_url
from apps.core.platforms.models import SocialAccount


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


# ── Phase 1 W1.2 — Revenue Headline Insight ─────────────────────────────────
#
# The single-sentence "what happened" surface on the Revenue Dashboard.
# 5 distinct kinds based on data state; each must produce a usable headline.

@pytest.mark.django_db
class TestRevenueHeadlineInsight:
    """Locks the headline insight contract used by both the Revenue
    Dashboard and (W1.3) the Daily Brief."""

    def test_no_pipeline_kind_for_brand_new_user(self, user):
        # Brand new user — no posts, no pixel, no conversions
        from apps.insight.analytics.revenue import get_revenue_headline_insight
        insight = get_revenue_headline_insight(user, days=7)
        assert insight["kind"] == "no_pipeline"
        assert insight["cta_url"]  # has a next-action
        assert "Open Studio" in insight["cta_text"]

    def test_no_pixel_kind_when_posts_published_no_events(self, user, social_account):
        # Has published posts but no Pixel events fired
        Post.objects.create(
            user=user, social_account=social_account, platform="instagram",
            content_text="Live post", status="published",
        )
        from apps.insight.analytics.revenue import get_revenue_headline_insight
        insight = get_revenue_headline_insight(user, days=7)
        assert insight["kind"] == "no_pixel"
        assert "Pixel" in insight["headline"]

    def test_pipeline_warming_when_events_but_no_conversions(self, user, social_account):
        from apps.insight.analytics.models import WebsiteEvent
        WebsiteEvent.objects.create(
            user=user, event_type="page_view",
            visitor_id="v1", session_id="s1",
            page_url="https://shop.co.ke/",
        )
        from apps.insight.analytics.revenue import get_revenue_headline_insight
        insight = get_revenue_headline_insight(user, days=7)
        assert insight["kind"] == "pipeline_warming"
        assert "Pixel is firing" in insight["headline"]

    def test_top_post_kind_when_revenue_attributed(self, user, social_account, post):
        from apps.insight.analytics.models import Conversion
        from decimal import Decimal
        Conversion.objects.create(
            user=user, post=post, social_account=social_account,
            conversion_type="sale", event_name="purchase",
            revenue=Decimal("12400"),
        )
        from apps.insight.analytics.revenue import get_revenue_headline_insight
        insight = get_revenue_headline_insight(user, days=7)
        assert insight["kind"] == "top_post"
        # The Instagram post content was "Try our new dress! Shop now …"
        assert "Instagram" in insight["headline"]
        assert "12,400" in insight["headline"]
        assert insight["post_revenue"] == 12400.0

    def test_no_revenue_in_window_when_old_conversion_exists(self, user, post):
        from apps.insight.analytics.models import Conversion
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        # Create a conversion outside the 7-day window
        c = Conversion.objects.create(
            user=user, post=post,
            conversion_type="sale", event_name="purchase",
            revenue=Decimal("5000"),
        )
        Conversion.objects.filter(pk=c.pk).update(
            created_at=timezone.now() - timedelta(days=30)
        )
        from apps.insight.analytics.revenue import get_revenue_headline_insight
        insight = get_revenue_headline_insight(user, days=7)
        assert insight["kind"] == "no_revenue_in_window"
        assert "?days=90" in insight["cta_url"]


# ── Phase 1 W1.3 — Daily Brief revenue context ──────────────────────────────

@pytest.mark.django_db
class TestDailyBriefRevenueContext:
    """The Daily Brief LLM prompt now branches on
    revenue_attribution.headline_insight.kind. If the helper stops getting
    into the brief context, the prompt falls back to generic language and
    the W1.2 work goes invisible."""

    def test_revenue_data_in_brief_includes_headline_insight(self, user):
        from apps.create.briefs.tasks import _gather_brief_data
        data = _gather_brief_data(user)

        assert "revenue_attribution" in data
        ra = data["revenue_attribution"] or {}
        assert "headline_insight" in ra, (
            "Daily Brief LLM context must carry the headline_insight block "
            "or the W1.3 prompt rewrite has nothing to read."
        )
        # Brand-new user should land on no_pipeline kind
        assert ra["headline_insight"]["kind"] == "no_pipeline"

    def test_headline_insight_carries_through_with_revenue(self, user, social_account, post):
        from apps.insight.analytics.models import Conversion
        from decimal import Decimal
        Conversion.objects.create(
            user=user, post=post, social_account=social_account,
            conversion_type="sale", event_name="purchase",
            revenue=Decimal("8500"),
        )
        from apps.create.briefs.tasks import _gather_brief_data
        data = _gather_brief_data(user)
        insight = (data.get("revenue_attribution") or {}).get("headline_insight")
        assert insight is not None
        assert insight["kind"] == "top_post"
        assert "8,500" in insight["headline"]


# ── Phase 1 W1.4 — Home page revenue stat card ──────────────────────────────

@pytest.mark.django_db
class TestRevenueStatCard:
    """The 7-day attributed revenue stat with week-over-week delta that
    sits on the Daily Brief home page. If has_data goes False, the
    template hides the card entirely so a new user sees nothing
    misleading."""

    def test_brand_new_user_has_no_data(self, user):
        from apps.insight.analytics.revenue import get_revenue_stat_card
        stat = get_revenue_stat_card(user)
        assert stat["has_data"] is False
        assert stat["current_kes"] == 0
        assert stat["previous_kes"] == 0
        assert stat["direction"] == "flat"

    def test_up_direction_when_current_beats_previous(self, user, post):
        from apps.insight.analytics.models import Conversion
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        # KES 5000 last week
        Conversion.objects.create(
            user=user, post=post,
            conversion_type="sale", event_name="purchase",
            revenue=Decimal("5000"),
        )
        # KES 2000 the week before (backdate)
        c = Conversion.objects.create(
            user=user, post=post,
            conversion_type="sale", event_name="purchase",
            revenue=Decimal("2000"),
        )
        Conversion.objects.filter(pk=c.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        from apps.insight.analytics.revenue import get_revenue_stat_card
        stat = get_revenue_stat_card(user)
        assert stat["has_data"] is True
        assert stat["current_kes"] == 5000.0
        assert stat["previous_kes"] == 2000.0
        assert stat["direction"] == "up"
        assert stat["delta_pct"] == 150.0  # (5000-2000)/2000 * 100

    def test_first_week_revenue_is_100_pct_up(self, user, post):
        # No previous-week data — current=KES X should read as +100% "new"
        from apps.insight.analytics.models import Conversion
        from decimal import Decimal
        Conversion.objects.create(
            user=user, post=post,
            conversion_type="sale", event_name="purchase",
            revenue=Decimal("3500"),
        )
        from apps.insight.analytics.revenue import get_revenue_stat_card
        stat = get_revenue_stat_card(user)
        assert stat["current_kes"] == 3500.0
        assert stat["previous_kes"] == 0
        assert stat["delta_pct"] == 100.0
        assert stat["direction"] == "up"
