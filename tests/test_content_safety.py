"""Tests for content safety moderation, fail-closed behavior, and publish blocks."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.accounts.models import User, UserProfile
from apps.content.models import ContentSafetyIncident, Post, SystemSafetyConfig
from apps.content.safety import (
    POLICY_BLOCK_MESSAGE,
    SafetyResult,
    _parse_moderation_response,
    apply_user_snap_block,
    block_post_for_policy,
    check_image_safe,
    check_post_safe,
    check_text_safe,
    clear_snap_block_for_dismissed_incident,
    content_safety_checks_running,
    content_safety_enabled,
    content_safety_staff_paused,
    is_sexual_policy_violation,
    is_snap_blocked,
    record_content_safety_incident,
)
from apps.content.tasks import publish_post
from apps.platforms.models import SocialAccount


@pytest.fixture
def user_b(db):
    u = User.objects.create_user(
        username="otheruser",
        email="other@kova.ai",
        password="TestPass123!",
        full_name="Other User",
    )
    UserProfile.objects.filter(user=u).update(plan="growth")
    u.refresh_from_db()
    return u


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


class TestStaffModerationToggle:
    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.content.safety._openrouter_moderate_image")
    def test_paused_skips_api_returns_safe(self, mock_mod, user):
        config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
        config.content_safety_checks_enabled = False
        config.save()

        result = check_image_safe("https://cdn.example.com/x.jpg", user=user)

        assert result.safe is True
        assert content_safety_staff_paused() is True
        assert content_safety_checks_running() is False
        mock_mod.assert_not_called()

    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.content.safety._openrouter_moderate_image")
    def test_enabled_calls_api(self, mock_mod, user):
        config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
        config.content_safety_checks_enabled = True
        config.save()
        mock_mod.return_value = SafetyResult(safe=True)

        check_image_safe("https://cdn.example.com/x.jpg", user=user)

        mock_mod.assert_called_once()

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_paused_skips_blocklist(self, user):
        config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
        config.content_safety_checks_enabled = False
        config.save()

        result = check_text_safe("buy my porn collection", user=user)

        assert result.safe is True

    @override_settings(CONTENT_SAFETY_ENABLED=False)
    def test_env_off_staff_pause_has_no_effect(self):
        config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
        config.content_safety_checks_enabled = False
        config.save()

        assert content_safety_staff_paused() is False
        assert content_safety_checks_running() is False


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


class TestSexualOnlyPolicy:
    def test_construction_scene_allowed(self):
        result = _parse_moderation_response({
            "safe": False,
            "severity": 72,
            "categories": ["graphic_violence"],
            "reasons": ["construction site with scaffolding"],
        })
        assert result.safe is True
        assert result.categories == []

    def test_architecture_low_severity_allowed(self):
        result = _parse_moderation_response({
            "safe": False,
            "severity": 60,
            "categories": ["sexual"],
            "reasons": ["building facade might look suggestive"],
        })
        assert result.safe is True

    def test_explicit_sexual_content_blocked(self):
        result = _parse_moderation_response({
            "safe": False,
            "severity": 95,
            "categories": ["porn"],
            "reasons": ["explicit sexual acts visible"],
        })
        assert result.safe is False
        assert "porn" in result.categories
        assert is_sexual_policy_violation(result) is True

    @override_settings(CONTENT_SAFETY_ENABLED=True, OPENROUTER_API_KEY="test-key")
    @patch("apps.content.safety._openrouter_moderate_image")
    def test_construction_image_no_incident_path(self, mock_mod, user):
        mock_mod.return_value = _parse_moderation_response({
            "safe": False,
            "severity": 72,
            "categories": [],
            "reasons": ["construction site with workers in hard hats"],
        })
        result = check_image_safe("https://cdn.example.com/building.jpg", user=user)
        assert result.safe is True
        assert is_sexual_policy_violation(result) is False
        assert ContentSafetyIncident.objects.filter(user=user).count() == 0

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_borderline_sexual_no_snap_block(self, user):
        borderline = SafetyResult(
            safe=True,
            severity=70,
            categories=["sexual"],
            reasons=["uncertain"],
        )
        incident = ContentSafetyIncident.objects.create(
            user=user,
            source=ContentSafetyIncident.Source.UPLOAD,
            reasons=borderline.reasons,
            categories=borderline.categories,
            severity=borderline.severity,
            action_taken="snap_upload_blocked",
        )
        apply_user_snap_block(user, incident, borderline)
        assert is_snap_blocked(user)[0] is False

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    @patch("apps.content.safety.check_post_safe")
    def test_block_post_no_strike_without_sexual_category(self, mock_check, approved_post):
        mock_check.return_value = SafetyResult(
            safe=False,
            reasons=["Matched blocked pattern"],
            severity=100,
            categories=["policy"],
        )
        block_post_for_policy(approved_post, mock_check.return_value, source="publish")
        approved_post.user.refresh_from_db()
        assert approved_post.status == Post.Status.BLOCKED
        assert (approved_post.user.profile.content_safety_strike_count or 0) == 0


class TestPerUserSnapBlock:
    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_user_a_incident_does_not_block_user_b_snap(self, user, user_b):
        unsafe = SafetyResult(
            safe=False,
            reasons=["explicit nudity"],
            severity=95,
            categories=["nudity"],
        )
        incident = record_content_safety_incident(
            user=user,
            source=ContentSafetyIncident.Source.UPLOAD,
            result=unsafe,
            image_url="https://cdn.example.com/flagged.jpg",
            action_taken="snap_upload_blocked",
        )

        blocked_a, _ = is_snap_blocked(user)
        blocked_b, _ = is_snap_blocked(user_b)
        assert blocked_a is True
        assert blocked_b is False
        assert incident.pk is not None

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_global_auto_publish_unchanged_on_incident_create(self, user):
        config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
        config.auto_publish_paused = False
        config.save()

        record_content_safety_incident(
            user=user,
            source=ContentSafetyIncident.Source.UPLOAD,
            result=SafetyResult(
                safe=False,
                reasons=["pornographic content"],
                severity=100,
                categories=["porn"],
            ),
            action_taken="snap_upload_blocked",
        )

        config.refresh_from_db()
        assert config.auto_publish_paused is False

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_dismissed_incident_clears_snap_block(self, user):
        unsafe = SafetyResult(
            safe=False,
            reasons=["false alarm test"],
            severity=90,
            categories=["nudity"],
        )
        incident = record_content_safety_incident(
            user=user,
            source=ContentSafetyIncident.Source.UPLOAD,
            result=unsafe,
            action_taken="snap_upload_blocked",
        )
        assert is_snap_blocked(user)[0] is True

        incident.review_status = ContentSafetyIncident.ReviewStatus.DISMISSED
        incident.save(update_fields=["review_status"])
        clear_snap_block_for_dismissed_incident(incident)

        user.refresh_from_db()
        assert is_snap_blocked(user)[0] is False

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_api_failure_does_not_apply_snap_block(self, user):
        api_fail = SafetyResult(
            safe=False,
            reasons=["Moderation API error"],
            severity=100,
            api_failed=True,
        )
        incident = ContentSafetyIncident.objects.create(
            user=user,
            source=ContentSafetyIncident.Source.UPLOAD,
            reasons=api_fail.reasons,
            severity=api_fail.severity,
            action_taken="snap_upload_blocked",
        )
        apply_user_snap_block(user, incident, api_fail)

        assert is_snap_blocked(user)[0] is False
