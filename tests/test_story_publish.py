"""Tests for Instagram and Facebook Stories publish routing."""

from unittest.mock import MagicMock, patch

from apps.platforms.providers.base import PublishResult
from apps.platforms.providers.instagram_facebook import FacebookProvider, InstagramProvider


class TestInstagramStoryPublish:
    def test_publish_post_routes_stories_media_type(self):
        provider = InstagramProvider()
        with patch.object(provider, "publish_story") as mock_story:
            mock_story.return_value = PublishResult(success=True, platform_post_id="ig_story_1")
            provider.publish_post(
                "user-token",
                "caption",
                media_urls=["https://cdn.example.com/story.jpg"],
                ig_user_id="ig123",
                page_access_token="page-token",
                media_type="STORIES",
            )
            mock_story.assert_called_once()
            assert mock_story.call_args[0][0] == "user-token"
            assert mock_story.call_args[1]["media_urls"] == ["https://cdn.example.com/story.jpg"]

    def test_publish_story_uses_page_access_token(self):
        provider = InstagramProvider()
        with patch.object(provider, "_publish_story") as mock_internal:
            mock_internal.return_value = PublishResult(success=True, platform_post_id="1")
            provider.publish_story(
                "user-token",
                media_urls=["https://cdn.example.com/story.mp4"],
                ig_user_id="ig123",
                page_access_token="page-token",
            )
            args = mock_internal.call_args[0]
            assert args[1] == "page-token"

    @patch("apps.platforms.providers.instagram_facebook.httpx.Client")
    def test_publish_story_image_container_flow(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        container_resp = MagicMock()
        container_resp.json.return_value = {"id": "container123"}
        container_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.json.return_value = {"status_code": "FINISHED"}
        status_resp.raise_for_status = MagicMock()

        publish_resp = MagicMock()
        publish_resp.json.return_value = {"id": "story_media_1"}
        publish_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [container_resp, publish_resp]
        mock_client.get.return_value = status_resp

        provider = InstagramProvider()
        result = provider.publish_story(
            "page-token",
            media_urls=["https://cdn.example.com/story.jpg"],
            ig_user_id="ig123",
            page_access_token="page-token",
        )

        assert result.success is True
        assert result.platform_post_id == "story_media_1"
        first_call = mock_client.post.call_args_list[0]
        assert first_call[1]["data"]["media_type"] == "STORIES"
        assert first_call[1]["data"]["image_url"] == "https://cdn.example.com/story.jpg"


class TestFacebookStoryPublish:
    def test_publish_post_routes_stories_media_type(self):
        provider = FacebookProvider()
        with patch.object(provider, "publish_story") as mock_story:
            mock_story.return_value = PublishResult(success=True, platform_post_id="fb_story_1")
            provider.publish_post(
                "token",
                "caption",
                media_urls=["https://cdn.example.com/story.jpg"],
                page_id="page1",
                page_access_token="page_token",
                media_type="STORIES",
            )
            mock_story.assert_called_once()

    @patch("apps.platforms.providers.instagram_facebook.httpx.Client")
    def test_publish_photo_story_two_step_flow(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        upload_resp = MagicMock()
        upload_resp.json.return_value = {"id": "photo123"}
        upload_resp.raise_for_status = MagicMock()

        story_resp = MagicMock()
        story_resp.json.return_value = {
            "success": True,
            "post_id": "story_post_1",
            "url": "https://www.facebook.com/stories/story_post_1",
        }
        story_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [upload_resp, story_resp]

        provider = FacebookProvider()
        result = provider.publish_story(
            "page_token",
            media_urls=["https://cdn.example.com/story.jpg"],
            page_id="page1",
            page_access_token="page_token",
        )

        assert result.success is True
        assert result.platform_post_id == "story_post_1"
        assert mock_client.post.call_count == 2
        assert "photo_stories" in mock_client.post.call_args_list[1][0][0]

    @patch("apps.platforms.providers.instagram_facebook.httpx.Client")
    def test_publish_video_story_three_phase_flow(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        start_resp = MagicMock()
        start_resp.json.return_value = {
            "video_id": "vid123",
            "upload_url": "https://rupload.facebook.com/video-upload/v25.0/vid123",
        }
        start_resp.raise_for_status = MagicMock()

        upload_resp = MagicMock()
        upload_resp.raise_for_status = MagicMock()

        finish_resp = MagicMock()
        finish_resp.json.return_value = {
            "success": True,
            "post_id": "story_vid_post",
            "url": "https://www.facebook.com/stories/story_vid_post",
        }
        finish_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [start_resp, upload_resp, finish_resp]

        provider = FacebookProvider()
        result = provider.publish_story(
            "page_token",
            media_urls=["https://cdn.example.com/story.mp4"],
            page_id="page1",
            page_access_token="page_token",
        )

        assert result.success is True
        assert result.platform_post_id == "story_vid_post"
        assert mock_client.post.call_count == 3
