"""Tests for Create Agent template fallback posts."""

import pytest

from apps.create.agents.create_agent import build_fallback_posts


@pytest.mark.django_db
class TestBuildFallbackPosts:
    def test_product_seed_produces_platform_posts(self, user_factory, product_factory):
        user = user_factory()
        product = product_factory(
            user=user,
            name="Test Widget",
            description="A great widget for everyday use.",
            price=29.99,
        )
        from apps.create.content.models import ContentSeed

        seed = ContentSeed.objects.create(
            user=user,
            product=product,
            idea="Launch our new widget",
        )
        platforms = [
            {"platform": "instagram", "username": "shop"},
            {"platform": "facebook", "username": "shop"},
        ]

        strategy, posts = build_fallback_posts(seed, platforms)

        assert "Template drafts" in strategy
        assert len(posts) == 2
        assert posts[0]["platform"] == "instagram"
        assert "widget" in posts[0]["content_text"].lower()
        assert posts[0]["framework_used"] == "Template fallback"
