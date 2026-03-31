"""
YouTube OAuth 2.0 Provider (Google APIs).

Uses YouTube Data API v3 for video uploads and analytics.
OAuth 2.0 flow through Google — same credentials as Google Cloud Console.

Capability matrix:
─────────────────────────────────────────────────────────────────────
CAPABILITY                           │ API ENDPOINT
─────────────────────────────────────────────────────────────────────
Upload video                         │ POST youtube.googleapis.com/upload/youtube/v3/videos
Update video metadata                │ PUT /youtube/v3/videos
Get video metrics                    │ GET /youtube/v3/videos (statistics)
Get channel info                     │ GET /youtube/v3/channels
List videos                          │ GET /youtube/v3/search
Get comments                         │ GET /youtube/v3/commentThreads
Reply to comment                     │ POST /youtube/v3/comments
─────────────────────────────────────────────────────────────────────
Docs: https://developers.google.com/youtube/v3
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

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_API_BASE = "https://www.googleapis.com/youtube/v3"
YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

YT_SCOPES = " ".join([
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
])


class YouTubeProvider(BaseProvider):
    platform_name = "youtube"

    def __init__(self):
        self.client_id = getattr(settings, "YOUTUBE_CLIENT_ID", "")
        self.client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": YT_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        with httpx.Client() as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
            resp.raise_for_status()
            tokens = resp.json()

            # Fetch channel info
            channel_resp = client.get(
                f"{YT_API_BASE}/channels",
                params={"part": "snippet,statistics", "mine": "true"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            channel_resp.raise_for_status()
            channels = channel_resp.json().get("items", [])
            channel = channels[0] if channels else {}
            snippet = channel.get("snippet", {})
            stats = channel.get("statistics", {})

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

        return OAuthResult(
            platform_user_id=channel.get("id", ""),
            username=snippet.get("customUrl", snippet.get("title", "")),
            display_name=snippet.get("title", ""),
            avatar_url=snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            access_token=tokens.get("access_token", ""),
            refresh_token=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
            token_scope=tokens.get("scope", ""),
            metadata={
                "subscriber_count": stats.get("subscriberCount", "0"),
                "video_count": stats.get("videoCount", "0"),
                "view_count": stats.get("viewCount", "0"),
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        with httpx.Client() as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
            resp.raise_for_status()
            tokens = resp.json()

        result = {"access_token": tokens["access_token"]}
        if "refresh_token" in tokens:
            result["refresh_token"] = tokens["refresh_token"]
        if "expires_in" in tokens:
            result["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        return result

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Publish to YouTube. For YouTube, content is the description.
        kwargs can include: title, tags, category_id, privacy_status.
        media_urls[0] should be the video file URL.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        title = kwargs.get("title", content[:100])
        tags = kwargs.get("tags", [])
        privacy = kwargs.get("privacy_status", "public")

        # If we have a video URL, download and upload it
        if media_urls:
            try:
                with httpx.Client(timeout=120) as client:
                    # Download the video
                    video_resp = client.get(media_urls[0])
                    video_resp.raise_for_status()
                    video_data = video_resp.content

                    # Resumable upload — initiate
                    metadata = {
                        "snippet": {
                            "title": title,
                            "description": content,
                            "tags": tags,
                            "categoryId": kwargs.get("category_id", "22"),  # 22 = People & Blogs
                        },
                        "status": {
                            "privacyStatus": privacy,
                            "selfDeclaredMadeForKids": False,
                        },
                    }

                    init_resp = client.post(
                        f"{YT_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
                        json=metadata,
                        headers={
                            **headers,
                            "Content-Type": "application/json; charset=UTF-8",
                            "X-Upload-Content-Type": "video/*",
                            "X-Upload-Content-Length": str(len(video_data)),
                        },
                    )
                    init_resp.raise_for_status()
                    upload_url = init_resp.headers.get("Location", "")

                    if not upload_url:
                        return PublishResult(success=False, error="No upload URL returned")

                    # Upload the video data
                    upload_resp = client.put(
                        upload_url,
                        content=video_data,
                        headers={"Content-Type": "video/*"},
                    )
                    upload_resp.raise_for_status()
                    video_id = upload_resp.json().get("id", "")

                    return PublishResult(
                        success=True,
                        platform_post_id=video_id,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                    )
            except httpx.HTTPStatusError as e:
                logger.error("YouTube upload failed: %s", e.response.text)
                return PublishResult(success=False, error=str(e))
        else:
            # Text-only "community post" — requires channel to have community tab
            # For now, return an error since YouTube needs video content
            return PublishResult(
                success=False,
                error="YouTube requires video content. Text-only community posts are not yet supported via API.",
            )

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{YT_API_BASE}/videos",
                    params={"part": "statistics", "id": platform_post_id},
                    headers=headers,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if not items:
                    return PostMetrics()
                stats = items[0].get("statistics", {})
                return PostMetrics(
                    likes=int(stats.get("likeCount", 0)),
                    comments=int(stats.get("commentCount", 0)),
                    shares=0,  # YouTube doesn't expose share count via API
                    impressions=int(stats.get("viewCount", 0)),
                )
        except httpx.HTTPStatusError as e:
            logger.error("YouTube metrics failed: %s", e.response.text)
            return PostMetrics()

    def get_comments(self, access_token: str, post_id: str, **kwargs) -> list[dict]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{YT_API_BASE}/commentThreads",
                    params={
                        "part": "snippet",
                        "videoId": post_id,
                        "maxResults": 20,
                        "order": "time",
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                comments = []
                for item in resp.json().get("items", []):
                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append({
                        "id": item["id"],
                        "author_id": snippet.get("authorChannelId", {}).get("value", ""),
                        "author_name": snippet.get("authorDisplayName", ""),
                        "text": snippet.get("textDisplay", ""),
                        "created_at": snippet.get("publishedAt", ""),
                    })
                return comments
        except httpx.HTTPStatusError as e:
            logger.error("YouTube comments failed: %s", e.response.text)
            return []

    def reply_to_comment(self, access_token: str, comment_id: str,
                         message: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{YT_API_BASE}/comments",
                    params={"part": "snippet"},
                    json={
                        "snippet": {
                            "parentId": comment_id,
                            "textOriginal": message,
                        }
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                return {"id": resp.json().get("id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("YouTube reply failed: %s", e.response.text)
            return {"error": str(e), "success": False}


# Auto-register
register_provider(YouTubeProvider())
