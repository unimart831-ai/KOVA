"""
TikTok Provider — OAuth 2.0 + Content Posting API.

TikTok uses a specific Content Posting API for publishing. The OAuth flow is
similar to standard OAuth 2.0 but with TikTok-specific endpoints.

Docs: https://developers.tiktok.com/doc/content-posting-api-get-started/
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from django.conf import settings

from apps.platforms.providers.base import (
    BaseProvider, OAuthResult, PostMetrics, PublishResult,
)
from apps.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"

TIKTOK_SCOPES = "user.info.basic,video.publish,video.list"


class TikTokProvider(BaseProvider):
    """TikTok provider using Content Posting API."""
    platform_name = "tiktok"

    def __init__(self):
        self.client_key = getattr(settings, "TIKTOK_CLIENT_KEY", "")
        self.client_secret = getattr(settings, "TIKTOK_CLIENT_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_key": self.client_key,
            "redirect_uri": redirect_uri,
            "scope": TIKTOK_SCOPES,
            "state": state,
            "response_type": "code",
        }
        return f"{TIKTOK_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        with httpx.Client() as client:
            # Exchange code for token
            resp = client.post(
                TIKTOK_TOKEN_URL,
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token", "")
            open_id = tokens.get("open_id", "")

            # Fetch user info
            user_resp = client.get(
                f"{TIKTOK_API_BASE}/user/info/",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "open_id,union_id,avatar_url,display_name,username"},
            )
            user_resp.raise_for_status()
            user_data = user_resp.json().get("data", {}).get("user", {})

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

        return OAuthResult(
            platform_user_id=open_id or user_data.get("open_id", ""),
            username=user_data.get("username", ""),
            display_name=user_data.get("display_name", ""),
            avatar_url=user_data.get("avatar_url", ""),
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
            token_scope=TIKTOK_SCOPES,
            metadata={},
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        with httpx.Client() as client:
            resp = client.post(
                TIKTOK_TOKEN_URL,
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh_token),
            "expires_in": tokens.get("expires_in"),
        }

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        TikTok Content Posting API requires a video URL.
        Flow: 1) Initialize upload → 2) Upload video → 3) Publish.
        """
        if not media_urls:
            return PublishResult(
                success=False,
                error="TikTok requires a video URL for publishing.",
            )

        video_url = media_urls[0]

        try:
            with httpx.Client() as client:
                # Step 1: Initialize upload via pull URL
                init_resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/video/init/",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "post_info": {
                            "title": content[:150],  # TikTok title limit
                            "privacy_level": kwargs.get("privacy_level", "SELF_ONLY"),
                            "disable_duet": False,
                            "disable_stitch": False,
                            "disable_comment": False,
                        },
                        "source_info": {
                            "source": "PULL_FROM_URL",
                            "video_url": video_url,
                        },
                    },
                )
                init_resp.raise_for_status()
                init_data = init_resp.json().get("data", {})
                publish_id = init_data.get("publish_id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=publish_id,
                    url="",  # TikTok URL available after processing completes
                    metadata={"status": "processing", "publish_id": publish_id},
                )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def check_publish_status(self, access_token: str, publish_id: str) -> dict:
        """Check the status of a video upload."""
        with httpx.Client() as client:
            resp = client.post(
                f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"publish_id": publish_id},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/video/query/",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "filters": {"video_ids": [platform_post_id]},
                        "fields": ["like_count", "comment_count", "share_count", "view_count"],
                    },
                )
                resp.raise_for_status()
                videos = resp.json().get("data", {}).get("videos", [])
                if not videos:
                    return PostMetrics()
                video = videos[0]
                return PostMetrics(
                    likes=video.get("like_count", 0),
                    comments=video.get("comment_count", 0),
                    shares=video.get("share_count", 0),
                    impressions=video.get("view_count", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    def get_user_info(self, access_token: str) -> dict:
        with httpx.Client() as client:
            resp = client.get(
                f"{TIKTOK_API_BASE}/user/info/",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "open_id,union_id,avatar_url,display_name,username,follower_count"},
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("user", {})


# Auto-register
register_provider(TikTokProvider())
