"""Tests for cross-platform Reel / video publish routing."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.content.models import Post
from apps.content.tasks import (
    _fail_post,
    _is_unreachable_platform_url,
    _platform_media_url,
    _public_url_for_file,
    _resolve_reel_publish_video_url,
    _reel_video_url,
    _resolve_tiktok_privacy,
)
from apps.platforms.providers.base import PublishResult
from apps.platforms.providers.instagram_facebook import (
    FacebookProvider,
    InstagramProvider,
    _graph_api_error_text,
    _reel_url_from_media_list,
)


class TestReelPublishHelpers:
    def test_reel_video_url_picks_mp4(self):
        urls = [
            "https://cdn.example.com/frame.jpg",
            "https://cdn.example.com/reel.mp4",
        ]
        assert _reel_video_url(urls) == urls[1]

    def test_reel_url_from_media_list_ignores_images(self):
        urls = [
            "https://cdn.example.com/frame.jpg",
            "https://cdn.example.com/reel.mp4?X-Amz-Signature=abc",
        ]
        assert _reel_url_from_media_list(urls) == urls[1]
        assert _reel_url_from_media_list(["https://cdn.example.com/frame.jpg"]) == ""

    def test_resolve_tiktok_privacy_defaults_self_only(self):
        account = MagicMock(metadata={})
        assert _resolve_tiktok_privacy(account) == "SELF_ONLY"

    def test_resolve_tiktok_privacy_from_account_metadata(self):
        account = MagicMock(metadata={"default_privacy_level": "PUBLIC_TO_EVERYONE"})
        assert _resolve_tiktok_privacy(account) == "PUBLIC_TO_EVERYONE"

    def test_unreachable_platform_url_detects_localhost(self):
        assert _is_unreachable_platform_url("http://localhost/media/x.jpg") is True
        assert _is_unreachable_platform_url("https://cdn.example.com/x.jpg") is False

    def test_platform_media_url_passes_external_https(self):
        url = "https://images.photoroom.com/product.jpg"
        assert _platform_media_url(url) == url

    @patch("apps.content.tasks._presigned_storage_url")
    @patch("apps.content.tasks._storage_custom_domain", return_value="")
    def test_public_url_for_platform_api_uses_presigned(self, _domain, mock_presign):
        mock_presign.return_value = "https://r2.example.com/signed.mp4?sig=1"
        assert _public_url_for_file("reel_videos/test.mp4", for_platform_api=True) == mock_presign.return_value
        mock_presign.assert_called_once_with("reel_videos/test.mp4")

    @patch("apps.content.tasks._public_url_for_file")
    def test_resolve_reel_publish_video_from_attachment(self, mock_pub):
        mock_pub.return_value = "https://r2.example.com/signed.mp4?sig=1"
        post = MagicMock()
        post.visual_metadata = {}
        post.media_urls = ["https://cdn.example.com/frame.jpg"]
        att = MagicMock()
        att.file.name = "reel_videos/abc.mp4"
        post.attachments.filter.return_value.order_by.return_value = [att]
        url = _resolve_reel_publish_video_url(post)
        assert url == "https://r2.example.com/signed.mp4?sig=1"
        mock_pub.assert_called_with("reel_videos/abc.mp4", for_platform_api=True)

    def test_graph_api_error_text_parses_json(self):
        response = MagicMock(spec=httpx.Response)
        response.json.return_value = {
            "error": {
                "message": "Invalid parameter",
                "error_user_msg": "Video URL is unreachable",
                "code": 100,
                "error_subcode": 2207026,
            }
        }
        text = _graph_api_error_text(response)
        assert "Invalid parameter" in text
        assert "Video URL is unreachable" in text
        assert "100" in text


@pytest.mark.django_db
class TestFailPostPersistence:
    def test_fail_post_sets_publish_error(self, user):
        from apps.platforms.models import SocialAccount

        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            username="test_ig",
            access_token="token",
            is_active=True,
        )
        post = Post.objects.create(
            user=user,
            social_account=account,
            platform="instagram",
            content_text="Test",
            status=Post.Status.PUBLISHING,
            post_format=Post.PostFormat.REEL,
        )
        _fail_post(post, "Instagram could not process your video: codec error")
        post.refresh_from_db()
        assert post.status == Post.Status.FAILED
        assert "codec error" in post.publish_error
        assert post.publish_failure_message == post.publish_error


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


class TestInstagramReelPublish:
    def test_publish_post_uses_page_access_token(self):
        provider = InstagramProvider()
        with patch.object(provider, "_publish_reels") as mock_reels:
            mock_reels.return_value = PublishResult(success=True, platform_post_id="1")
            provider.publish_post(
                "user-token",
                "caption",
                media_urls=["https://cdn.example.com/reel.mp4"],
                ig_user_id="ig123",
                page_access_token="page-token",
                media_type="REELS",
                video_url="https://cdn.example.com/reel.mp4",
            )
            args = mock_reels.call_args[0]
            assert args[1] == "page-token"

    def test_publish_post_routes_reels_not_first_image(self):
        provider = InstagramProvider()
        with patch.object(provider, "_publish_reels") as mock_reels:
            mock_reels.return_value = PublishResult(success=True, platform_post_id="1")
            provider.publish_post(
                "token",
                "caption",
                media_urls=[
                    "https://cdn.example.com/slide.jpg",
                    "https://cdn.example.com/reel.mp4",
                ],
                ig_user_id="ig123",
                media_type="REELS",
                video_url="https://cdn.example.com/reel.mp4",
            )
            mock_reels.assert_called_once()
            assert mock_reels.call_args[0][4] == "https://cdn.example.com/reel.mp4"
