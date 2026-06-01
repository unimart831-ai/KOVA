"""Tests for content safety moderation, fail-closed behavior, and publish blocks."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.content.models import ContentSafetyIncident, Post
from apps.content.safety import (
    POLICY_BLOCK_MESSAGE,
    SafetyResult,
    check_image_safe,
    check_post_safe,
    check_text_safe,
    content_safety_enabled,
)
from apps.content.tasks import publish_post
from apps.platforms.models import SocialAccount


@pytest.fixture
def social_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        username="testshop",
        is_active=True,
        access_token="test-token",
    )


@pytest.fixture
def approved_post(user, social_account):
    return Post.objects.create(
        user=user,
        social_account=social_account,
        platform="instagram",
        content_text="Fresh mangoes from our farm — order today!",
        status=Post.Status.APPROVED,
        media_urls=["https://cdn.example.com/mango.jpg"],
    )


class TestSafetyResult:
    def test_blocked_property(self):
        safe = SafetyResult(safe=True)
        unsafe = SafetyResult(safe=False, reasons=["nudity"])
        assert safe.blocked is False
        assert unsafe.blocked is True


class TestContentSafetyEnabled:
    @override_settings(CONTENT_SAFETY_ENABLED=False)
    def test_disabled_by_default_in_base_settings(self):
        assert content_safety_enabled() is False

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_enabled_when_set(self):
        assert content_safety_enabled() is True


class TestCheckTextSafe:
    @override_settings(CONTENT_SAFETY_ENABLED=False)
    def test_blocklist_still_runs_when_disabled(self, user):
        result = check_text_safe("buy my porn collection", user=user)
        assert result.safe is False
        assert result.severity == 100

    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.content.safety._openrouter_moderate_text")
    def test_api_merged_when_enabled(self, mock_mod, user):
        mock_mod.return_value = SafetyResult(
            safe=False,
            reasons=["sexual content"],
            severity=90,
            categories=["sexual"],
        )
        result = check_text_safe("innocent product caption", user=user)
        assert result.safe is False
        assert "sexual" in result.categories


class TestFailClosed:
    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="")
    def test_image_fail_closed_no_api_key(self, user):
        result = check_image_safe("https://cdn.example.com/x.jpg", user=user)
        assert result.safe is False
        assert result.api_failed is True

    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.agents.llm._get_openrouter_client")
    def test_image_fail_closed_on_api_error(self, mock_client_fn, user):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        mock_client_fn.return_value = mock_client

        result = check_image_safe("https://cdn.example.com/x.jpg", user=user)
        assert result.safe is False
        assert result.api_failed is True


class TestCheckPostSafe:
    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.content.safety.check_image_safe")
    @patch("apps.content.safety.check_text_safe")
    def test_post_checks_text_and_images(self, mock_text, mock_image, approved_post):
        mock_text.return_value = SafetyResult(safe=True)
        mock_image.return_value = SafetyResult(
            safe=False,
            reasons=["explicit nudity"],
            severity=95,
            categories=["nudity"],
        )
        result = check_post_safe(approved_post)
        assert result.safe is False
        mock_image.assert_called_once()


class TestPublishPostBlocks:
    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.content.safety.check_post_safe")
    def test_publish_post_blocks_unsafe_content(self, mock_check, approved_post):
        mock_check.return_value = SafetyResult(
            safe=False,
            reasons=["pornographic content"],
            severity=100,
            categories=["porn"],
        )

        result = publish_post(str(approved_post.pk))

        approved_post.refresh_from_db()
        assert approved_post.status == Post.Status.BLOCKED
        assert POLICY_BLOCK_MESSAGE in approved_post.publish_error
        assert "error" in result
        assert ContentSafetyIncident.objects.filter(post=approved_post).exists()
