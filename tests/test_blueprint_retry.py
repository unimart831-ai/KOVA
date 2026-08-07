"""Tests for blueprint quality auto-retry."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.core.accounts.models import User
from apps.create.content.blueprint_retry import improve_low_blueprint_posts
from apps.create.content.models import ContentSeed


@pytest.fixture
def user(db):
    return User.objects.create_user(username="u", email="u@kova.ai", password="x")


def test_improve_skips_when_no_blueprint(user):
    seed = ContentSeed.objects.create(user=user, idea="Test")
    posts = [{"platform": "instagram", "content_text": "Hi"}]
    result = improve_low_blueprint_posts(posts, seed, user, "system", {"instagram": {"platform": "instagram"}})
    assert result == posts


@patch("apps.create.agents.create_agent._regenerate_single_platform")
def test_improve_retries_low_quality(mock_regen, user):
    seed = ContentSeed.objects.create(
        user=user,
        idea="Sell dresses",
        blueprint={
            "objective": "sell",
            "asset_type": "product",
            "title": "Dress",
            "platforms": [{"platform": "instagram", "format": "feed", "slots": {"hook": "", "caption": ""}}],
            "metadata": {},
        },
    )
    mock_regen.return_value = {
        "platform": "instagram",
        "content_text": "Stunning blue dress — KES 2500. Order on WhatsApp today. #fashion #nairobi",
        "post_format": "image",
    }
    posts = [{"platform": "instagram", "content_text": "Dress"}]
    platform_map = {"instagram": {"platform": "instagram", "username": "shop"}}
    result = improve_low_blueprint_posts(posts, seed, user, "system", platform_map, threshold=90)
    assert mock_regen.called
    assert "2500" in result[0]["content_text"]
