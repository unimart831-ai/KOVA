"""Tests for cross-platform Reel / video publish routing."""

from unittest.mock import MagicMock, patch

import pytest

from apps.content.tasks import _reel_video_url, _resolve_tiktok_privacy
from apps.platforms.providers.base import PublishResult
from apps.platforms.providers.instagram_facebook import FacebookProvider


class TestReelPublishHelpers:
    def test_reel_video_url_picks_mp4(self):
        urls = [
            "https://cdn.example.com/frame.jpg",
            "https://cdn.example.com/reel.mp4",
        ]
        assert _reel_video_url(urls) == urls[1]

    def test_resolve_tiktok_privacy_defaults_self_only(self):
        account = MagicMock(metadata={})
        assert _resolve_tiktok_privacy(account) == "SELF_ONLY"

    def test_resolve_tiktok_privacy_from_account_metadata(self):
        account = MagicMock(metadata={"default_privacy_level": "PUBLIC_TO_EVERYONE"})
        assert _resolve_tiktok_privacy(account) == "PUBLIC_TO_EVERYONE"


class TestFacebookReelPublish:
    @patch("apps.platforms.providers.instagram_facebook.httpx.Client")
    def test_publish_reel_three_phase_flow(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        start_resp = MagicMock()
        start_resp.json.return_value = {"video_id": "vid123"}
        start_resp.raise_for_status = MagicMock()

        upload_resp = MagicMock()
        upload_resp.raise_for_status = MagicMock()

        finish_resp = MagicMock()
        finish_resp.json.return_value = {"post_id": "post456", "success": True}
        finish_resp.raise_for_status = MagicMock()

        plink_resp = MagicMock()
        plink_resp.json.return_value = {"permalink_url": "https://www.facebook.com/reel/vid123"}

        mock_client.post.side_effect = [start_resp, upload_resp, finish_resp]
        mock_client.get.return_value = plink_resp

        provider = FacebookProvider()
        result = provider.publish_reel(
            "token",
            "https://cdn.example.com/reel.mp4",
            description="Test reel",
            page_id="page1",
            page_access_token="page_token",
        )

        assert result.success is True
        assert result.platform_post_id == "post456"
        assert "facebook.com" in result.url
        assert mock_client.post.call_count == 3

    def test_publish_post_routes_reels_media_type(self):
        provider = FacebookProvider()
        with patch.object(provider, "publish_reel") as mock_reel:
            mock_reel.return_value = PublishResult(success=True, platform_post_id="1")
            provider.publish_post(
                "token",
                "caption",
                media_urls=["https://cdn.example.com/reel.mp4"],
                page_id="page1",
                page_access_token="page_token",
                media_type="REELS",
            )
            mock_reel.assert_called_once()
