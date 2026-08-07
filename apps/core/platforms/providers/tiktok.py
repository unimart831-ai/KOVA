"""
TikTok Provider — Full Content Posting API + Display API integration.

Uses TikTok's Content Posting API for video and photo publishing, Display API
for listing user videos and fetching metrics, Creator Info API for
pre-publish validation, and aggregated engagement analytics.

Full capability matrix:
─────────────────────────────────────────────────────────────────────────────
CAPABILITY                           │ STATUS   │ API ENDPOINT / NOTES
─────────────────────────────────────────────────────────────────────────────
Connect via OAuth 2.0                │ ✅ LIVE  │ OAuth 2.0 flow (Login Kit)
Token refresh                        │ ✅ LIVE  │ /v2/oauth/token/
User profile                         │ ✅ LIVE  │ GET /v2/user/info/
Query creator info                   │ ✅ LIVE  │ POST /v2/post/publish/creator_info/query/
Publish video (pull from URL)        │ ✅ LIVE  │ POST /v2/post/publish/video/init/
Publish video (file upload)          │ ✅ LIVE  │ POST /v2/post/publish/video/init/ + PUT
Publish photo post (up to 35)        │ ✅ LIVE  │ POST /v2/post/publish/content/init/
Check publish status                 │ ✅ LIVE  │ POST /v2/post/publish/status/fetch/
List user's videos                   │ ✅ LIVE  │ POST /v2/video/list/
Query specific videos                │ ✅ LIVE  │ POST /v2/video/query/
Get video metrics                    │ ✅ LIVE  │ POST /v2/video/query/ (metrics fields)
Validate token                       │ ✅ LIVE  │ GET /v2/user/info/ check
Engagement summary (aggregate)       │ ✅ LIVE  │ Computed from /v2/video/list/ metrics
Read comments (Research API)         │ ⚠ GATED │ POST /v2/research/video/comment/list/
Read mentions                        │ ❌ NONE  │ No TikTok API exists
Write comments / replies             │ ❌ NONE  │ No public third-party API
Delete posts                         │ ❌ NONE  │ No public third-party API
─────────────────────────────────────────────────────────────────────────────

Permissions / Scopes:
  user.info.basic     — Read user profile
  video.publish       — Direct post to TikTok
  video.list          — List / query user's videos
  research.data.basic — (Optional) Research API comment access (gated)

Engagement strategy:
  TikTok engagement in Kova is METRICS-AWARE: we know comment/like/share/view
  counts per video via the Display API even without reading individual comments.
  The Research API (v2/research/video/comment/list/) provides full comment text
  but requires special approval. We attempt it and degrade gracefully.

Notes:
  - Unaudited API clients post to PRIVATE only (SELF_ONLY).
  - Video: PULL_FROM_URL or FILE_UPLOAD (chunked). MP4/MOV/WebM.
  - Photo: PULL_FROM_URL only. Up to 35 images.
  - TikTok doesn't have a public comments read/write API for third-party apps.
    The v2 Research API is gated behind application approval.
  - TikTok doesn't have a public delete post API for third-party apps.
  - TikTok doesn't have a mentions/notifications API for third-party apps.

Docs:
  https://developers.tiktok.com/doc/content-posting-api-get-started/
  https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
  https://developers.tiktok.com/doc/content-posting-api-reference-photo-post
  https://developers.tiktok.com/doc/display-api-get-started/
  https://developers.tiktok.com/doc/research-api-specs-query-video-comments/
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from django.conf import settings

from apps.core.platforms.providers.base import (
    BaseProvider, OAuthResult, PostMetrics, ProfileSnapshot, PublishResult,
)
from apps.core.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

# ── API endpoints ────────────────────────────────────────────────────────────
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TIKTOK_SCOPES = "user.info.basic,video.publish,video.list"


class TikTokProvider(BaseProvider):
    """Full TikTok integration via Content Posting API, Display API,
    Creator Info API, and engagement analytics."""

    platform_name = "tiktok"

    # Set to False after the first 403/401 from the Research API to avoid
    # repeated futile calls for the rest of this process's lifetime.
    _research_api_available = True

    def __init__(self):
        self.client_key = getattr(settings, "TIKTOK_CLIENT_KEY", "")
        self.client_secret = getattr(settings, "TIKTOK_CLIENT_SECRET", "")

    # ── Internal helpers ─────────────────────────────────────────────────

    def _api_headers(self, access_token: str) -> dict:
        """Standard headers for TikTok API calls."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _is_video(self, url: str) -> bool:
        """Check if a URL looks like a video file."""
        path = url.lower().split("?")[0]
        return path.endswith((".mp4", ".mov", ".webm", ".avi"))

    def _is_image(self, url: str) -> bool:
        """Check if a URL looks like an image file."""
        path = url.lower().split("?")[0]
        return path.endswith((
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
        ))

    # ── OAuth ────────────────────────────────────────────────────────────

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_key": self.client_key,
            "redirect_uri": redirect_uri,
            "scope": TIKTOK_SCOPES,
            "state": state,
            "response_type": "code",
        }
        return f"{TIKTOK_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str,
                        **kwargs) -> OAuthResult:
        with httpx.Client(timeout=30) as client:
            # Exchange code for tokens
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

            # Fetch user profile
            user_resp = client.get(
                f"{TIKTOK_API_BASE}/user/info/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                params={
                    "fields": "open_id,union_id,avatar_url,"
                              "display_name,username",
                },
            )
            user_resp.raise_for_status()
            user_data = (
                user_resp.json().get("data", {}).get("user", {})
            )

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=tokens["expires_in"]
            )

        return OAuthResult(
            platform_user_id=open_id or user_data.get("open_id", ""),
            username=user_data.get("username", ""),
            display_name=user_data.get("display_name", ""),
            avatar_url=user_data.get("avatar_url", ""),
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
            token_scope=TIKTOK_SCOPES,
            metadata={
                "open_id": open_id or user_data.get("open_id", ""),
                "union_id": user_data.get("union_id", ""),
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        with httpx.Client(timeout=30) as client:
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

        result = {"access_token": tokens["access_token"]}
        if "refresh_token" in tokens:
            result["refresh_token"] = tokens["refresh_token"]
        if "expires_in" in tokens:
            result["expires_in"] = tokens["expires_in"]
            result["expires_at"] = datetime.now(timezone.utc) + timedelta(
                seconds=tokens["expires_in"]
            )
        return result

    # ── Creator Info (pre-publish validation) ────────────────────────────

    def get_creator_info(self, access_token: str) -> dict:
        """Query creator info for privacy options and interaction settings.

        Returns dict with keys:
          creator_avatar_url, creator_username, creator_nickname,
          privacy_level_options, comment_disabled, duet_disabled,
          stitch_disabled, max_video_post_duration_sec
        """
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/creator_info/query/",
                    headers=self._api_headers(access_token),
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("error", {}).get("code") != "ok":
                    logger.warning(
                        "TikTok creator_info error: %s",
                        data.get("error", {}),
                    )
                    return {}

                return data.get("data", {})
        except httpx.HTTPStatusError as e:
            logger.error(
                "TikTok get_creator_info failed: %s", e.response.text
            )
            return {}

    # ── Publishing ───────────────────────────────────────────────────────

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list] = None,
                     **kwargs) -> PublishResult:
        """
        Publish to TikTok via Content Posting API.

        Auto-detects media type:
          - Video URLs (.mp4/.mov/.webm) → Direct Post video
          - Image URLs (.jpg/.png/etc.) → Photo post (up to 35)
          - No media → Error (TikTok requires media)

        Optional kwargs:
          privacy_level: PUBLIC_TO_EVERYONE | MUTUAL_FOLLOW_FRIENDS |
                         FOLLOWER_OF_CREATOR | SELF_ONLY (default)
          disable_duet, disable_stitch, disable_comment: bool
          video_cover_timestamp_ms: int
          brand_content_toggle, brand_organic_toggle: bool
          is_aigc: bool (label as AI-generated)
          auto_add_music: bool (photo posts — add recommended music)
          photo_cover_index: int (which photo as cover, 0-indexed)
          description: str (photo post description, max 4000 chars)
        """
        if not media_urls:
            return PublishResult(
                success=False,
                error="TikTok requires at least one media URL (video or photo).",
            )

        # Determine media type
        first = media_urls[0]
        if self._is_video(first):
            return self._publish_video(access_token, content, first, **kwargs)
        elif self._is_image(first) or len(media_urls) > 1:
            return self._publish_photo(
                access_token, content, media_urls, **kwargs
            )
        else:
            # Assume video for unknown extensions (TikTok's primary format)
            return self._publish_video(access_token, content, first, **kwargs)

    def _publish_video(self, access_token: str, content: str,
                       video_url: str, **kwargs) -> PublishResult:
        """Publish a video via PULL_FROM_URL Direct Post.

        TikTok downloads the video from the URL and processes it.
        Returns a publish_id for status tracking."""
        privacy = kwargs.get("privacy_level", "SELF_ONLY")

        post_info = {
            "title": content[:2200],
            "privacy_level": privacy,
            "disable_duet": kwargs.get("disable_duet", False),
            "disable_stitch": kwargs.get("disable_stitch", False),
            "disable_comment": kwargs.get("disable_comment", False),
        }

        # Scheduled publishing — TikTok requires "scheduled": True +
        # schedule_time as a Unix timestamp (min 15 min, max 10 days out).
        schedule_time = kwargs.get("schedule_time")
        if schedule_time:
            post_info["scheduled"] = True
            post_info["schedule_time"] = int(schedule_time)

        # Optional fields
        if kwargs.get("video_cover_timestamp_ms") is not None:
            post_info["video_cover_timestamp_ms"] = kwargs[
                "video_cover_timestamp_ms"
            ]
        if kwargs.get("brand_content_toggle") is not None:
            post_info["brand_content_toggle"] = kwargs["brand_content_toggle"]
        if kwargs.get("brand_organic_toggle") is not None:
            post_info["brand_organic_toggle"] = kwargs["brand_organic_toggle"]
        if kwargs.get("is_aigc"):
            post_info["is_aigc"] = True

        payload = {
            "post_info": post_info,
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            },
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/video/init/",
                    headers=self._api_headers(access_token),
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()

                error_code = result.get("error", {}).get("code", "")
                if error_code != "ok":
                    msg = result.get("error", {}).get("message", error_code)
                    return PublishResult(success=False, error=msg)

                data = result.get("data", {})
                publish_id = data.get("publish_id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=publish_id,
                    url="",  # Available after processing via status check
                    metadata={
                        "status": "processing",
                        "publish_id": publish_id,
                        "media_type": "video",
                    },
                )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok video publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def _publish_photo(self, access_token: str, content: str,
                       image_urls: list, **kwargs) -> PublishResult:
        """Publish a photo post via Content Posting API.

        Supports up to 35 images via PULL_FROM_URL.
        Uses /v2/post/publish/content/init/ endpoint."""
        privacy = kwargs.get("privacy_level", "SELF_ONLY")

        post_info = {
            "title": content[:90],  # Photo title max 90 chars
            "privacy_level": privacy,
            "disable_comment": kwargs.get("disable_comment", False),
        }

        # Photo-specific optional fields
        if kwargs.get("description"):
            post_info["description"] = kwargs["description"][:4000]
        if kwargs.get("auto_add_music") is not None:
            post_info["auto_add_music"] = kwargs["auto_add_music"]
        if kwargs.get("brand_content_toggle") is not None:
            post_info["brand_content_toggle"] = kwargs["brand_content_toggle"]
        if kwargs.get("brand_organic_toggle") is not None:
            post_info["brand_organic_toggle"] = kwargs["brand_organic_toggle"]

        # Limit to 35 images
        photos = image_urls[:35]
        cover_index = kwargs.get("photo_cover_index", 0)

        payload = {
            "media_type": "PHOTO",
            "post_mode": "DIRECT_POST",
            "post_info": post_info,
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_images": photos,
                "photo_cover_index": min(cover_index, len(photos) - 1),
            },
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/content/init/",
                    headers=self._api_headers(access_token),
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()

                error_code = result.get("error", {}).get("code", "")
                if error_code != "ok":
                    msg = result.get("error", {}).get("message", error_code)
                    return PublishResult(success=False, error=msg)

                data = result.get("data", {})
                publish_id = data.get("publish_id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=publish_id,
                    url="",
                    metadata={
                        "status": "processing",
                        "publish_id": publish_id,
                        "media_type": "photo",
                        "photo_count": len(photos),
                    },
                )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok photo publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def publish_video_upload(self, access_token: str, content: str,
                             video_bytes: bytes,
                             content_type: str = "video/mp4",
                             **kwargs) -> PublishResult:
        """Publish a video via FILE_UPLOAD (chunked upload).

        Use this when you have the video bytes directly rather than a URL.
        TikTok requires chunked upload for files."""
        privacy = kwargs.get("privacy_level", "SELF_ONLY")
        file_size = len(video_bytes)
        chunk_size = min(file_size, 10_000_000)  # 10 MB chunks
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        post_info = {
            "title": content[:2200],
            "privacy_level": privacy,
            "disable_duet": kwargs.get("disable_duet", False),
            "disable_stitch": kwargs.get("disable_stitch", False),
            "disable_comment": kwargs.get("disable_comment", False),
        }
        if kwargs.get("video_cover_timestamp_ms") is not None:
            post_info["video_cover_timestamp_ms"] = kwargs[
                "video_cover_timestamp_ms"
            ]
        if kwargs.get("is_aigc"):
            post_info["is_aigc"] = True

        try:
            with httpx.Client(timeout=120) as client:
                # 1. Initialize FILE_UPLOAD
                init_resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/video/init/",
                    headers=self._api_headers(access_token),
                    json={
                        "post_info": post_info,
                        "source_info": {
                            "source": "FILE_UPLOAD",
                            "video_size": file_size,
                            "chunk_size": chunk_size,
                            "total_chunk_count": total_chunks,
                        },
                    },
                )
                init_resp.raise_for_status()
                init_result = init_resp.json()

                error_code = init_result.get("error", {}).get("code", "")
                if error_code != "ok":
                    msg = init_result.get("error", {}).get(
                        "message", error_code
                    )
                    return PublishResult(success=False, error=msg)

                data = init_result.get("data", {})
                publish_id = data.get("publish_id", "")
                upload_url = data.get("upload_url", "")

                if not upload_url:
                    return PublishResult(
                        success=False, error="No upload_url returned"
                    )

                # 2. Upload chunks
                for i in range(total_chunks):
                    start = i * chunk_size
                    end = min(start + chunk_size, file_size)
                    chunk = video_bytes[start:end]

                    client.put(
                        upload_url,
                        content=chunk,
                        headers={
                            "Content-Type": content_type,
                            "Content-Length": str(len(chunk)),
                            "Content-Range": (
                                f"bytes {start}-{end - 1}/{file_size}"
                            ),
                        },
                        timeout=60,
                    ).raise_for_status()

                return PublishResult(
                    success=True,
                    platform_post_id=publish_id,
                    url="",
                    metadata={
                        "status": "processing",
                        "publish_id": publish_id,
                        "media_type": "video",
                        "upload_method": "FILE_UPLOAD",
                    },
                )
        except httpx.HTTPStatusError as e:
            logger.error(
                "TikTok video file upload failed: %s", e.response.text
            )
            return PublishResult(success=False, error=str(e))

    # ── Publish status tracking ──────────────────────────────────────────

    def check_publish_status(self, access_token: str,
                             publish_id: str) -> dict:
        """Check status of a video/photo upload.

        Returns dict with keys:
          status: PROCESSING_UPLOAD | PROCESSING_DOWNLOAD |
                  SEND_TO_USER_INBOX | PUBLISH_COMPLETE | FAILED
          fail_reason: (if FAILED) string explaining failure
          publicaly_available_post_id: list of post IDs if published
        """
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                    headers=self._api_headers(access_token),
                    json={"publish_id": publish_id},
                )
                resp.raise_for_status()
                result = resp.json()

                error_code = result.get("error", {}).get("code", "")
                if error_code != "ok":
                    return {
                        "status": "ERROR",
                        "error": result.get("error", {}).get(
                            "message", error_code
                        ),
                    }

                return result.get("data", {})
        except httpx.HTTPStatusError as e:
            logger.error(
                "TikTok check_publish_status failed: %s", e.response.text
            )
            return {"status": "ERROR", "error": str(e)}

    # ── Video listing & metrics ──────────────────────────────────────────

    def get_own_posts(self, access_token: str, count: int = 20,
                      **kwargs) -> list:
        """Fetch the user's recent TikTok videos via Display API.

        Returns list of video dicts with id, title, description,
        duration, cover, share_url, embed_link, and timestamps."""
        cursor = kwargs.get("cursor", 0)

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/video/list/",
                    headers=self._api_headers(access_token),
                    params={
                        "fields": "id,title,video_description,duration,"
                                  "cover_image_url,share_url,embed_link,"
                                  "create_time,like_count,comment_count,"
                                  "share_count,view_count",
                    },
                    json={"max_count": min(count, 20), "cursor": cursor},
                )
                resp.raise_for_status()
                result = resp.json()

            if result.get("error", {}).get("code") != "ok":
                logger.warning(
                    "TikTok video list error: %s",
                    result.get("error", {}),
                )
                return []

            data = result.get("data", {})
            videos = data.get("videos", [])

            posts = []
            for v in videos:
                create_ts = v.get("create_time", 0)
                posts.append({
                    "id": str(v.get("id", "")),
                    "text": v.get("title", ""),
                    "description": v.get("video_description", ""),
                    "duration": v.get("duration", 0),
                    "cover_image_url": v.get("cover_image_url", ""),
                    "url": v.get("share_url", ""),
                    "embed_link": v.get("embed_link", ""),
                    "created_at": (
                        datetime.fromtimestamp(
                            create_ts, tz=timezone.utc
                        ).isoformat()
                        if create_ts else ""
                    ),
                    "metrics": {
                        "likes": v.get("like_count", 0),
                        "comments": v.get("comment_count", 0),
                        "shares": v.get("share_count", 0),
                        "views": v.get("view_count", 0),
                    },
                })

            return posts
        except httpx.HTTPStatusError as e:
            logger.error(
                "TikTok get_own_posts failed: %s", e.response.text
            )
            return []

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """Fetch metrics for a specific video via /v2/video/query/."""
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/video/query/",
                    headers=self._api_headers(access_token),
                    params={
                        "fields": "id,like_count,comment_count,"
                                  "share_count,view_count",
                    },
                    json={
                        "filters": {
                            "video_ids": [platform_post_id],
                        },
                    },
                )
                resp.raise_for_status()
                result = resp.json()

                if result.get("error", {}).get("code") != "ok":
                    return PostMetrics()

                videos = result.get("data", {}).get("videos", [])
                if not videos:
                    return PostMetrics()

                v = videos[0]
                # TikTok view_count = unique viewers = reach, not impressions.
                # TikTok does not expose an impressions metric via Display API.
                return PostMetrics(
                    likes=v.get("like_count", 0),
                    comments=v.get("comment_count", 0),
                    shares=v.get("share_count", 0),
                    reach=v.get("view_count", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    # ── Engagement: comments, mentions, summary ──────────────────────────

    def get_comments(self, access_token: str, post_id: str,
                     max_count: int = 30, cursor: int = 0) -> list:
        """Attempt to fetch comments for a video.

        Tries the Research API endpoint POST /v2/research/video/comment/list/
        which requires special Research API approval from TikTok. If the app
        doesn't have Research API access (403/401), falls back gracefully to
        an empty list and disables further Research API attempts for the
        lifetime of this process via ``_research_api_available``.

        Returns list of dicts: [{"id", "author_name", "author_id", "text",
        "created_at"}, ...] or [] when unavailable.
        """
        if not TikTokProvider._research_api_available:
            logger.debug(
                "TikTok Research API previously flagged unavailable; "
                "skipping comment fetch for video %s", post_id,
            )
            return []

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/research/video/comment/list/",
                    headers=self._api_headers(access_token),
                    json={
                        "video_id": post_id,
                        "max_count": min(max_count, 100),
                        "cursor": cursor,
                    },
                )
                resp.raise_for_status()
                result = resp.json()

            error_info = result.get("error", {})
            if error_info.get("code") != "ok":
                error_code = error_info.get("code", "")
                if error_code in ("access_token_invalid", "scope_not_authorized"):
                    TikTokProvider._research_api_available = False
                    logger.info(
                        "TikTok Research API not authorized (%s); "
                        "disabling comment fetching. Apply for "
                        "research.data.basic scope to enable.",
                        error_code,
                    )
                    return []
                logger.warning(
                    "TikTok comment list error: %s", error_info,
                )
                return []

            comments_raw = result.get("data", {}).get("comments", [])
            comments = []
            for c in comments_raw:
                create_ts = c.get("create_time", 0)
                comments.append({
                    "id": str(c.get("id", "")),
                    "author_name": c.get("user", {}).get("display_name", ""),
                    "author_id": str(c.get("user", {}).get("id", "")),
                    "text": c.get("text", ""),
                    "created_at": (
                        datetime.fromtimestamp(
                            create_ts, tz=timezone.utc
                        ).isoformat()
                        if create_ts else ""
                    ),
                })

            logger.debug(
                "TikTok Research API returned %d comments for video %s",
                len(comments), post_id,
            )
            return comments

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                TikTokProvider._research_api_available = False
                logger.info(
                    "TikTok Research API returned %d; disabling comment "
                    "fetching for this process. Apply for "
                    "research.data.basic scope to enable.",
                    e.response.status_code,
                )
                return []
            logger.error(
                "TikTok get_comments failed: %s", e.response.text,
            )
            return []
        except Exception as e:
            logger.error("TikTok get_comments unexpected error: %s", e)
            return []

    def get_mentions(self, access_token: str,
                     since_id: Optional[str] = None) -> list:
        """Return mentions/notifications directed at the user.

        TikTok does not provide a mentions or notifications API for
        third-party applications. There is no endpoint to discover when
        another user @-mentions you in a comment, caption, or duet.

        This method exists to satisfy the engagement interface contract
        and always returns an empty list.
        """
        logger.debug(
            "TikTok get_mentions called — no API exists; returning empty. "
            "since_id=%s", since_id,
        )
        return []

    def get_engagement_summary(self, access_token: str,
                               count: int = 10) -> dict:
        """Aggregate engagement metrics across recent videos.

        Uses the Display API (get_own_posts) to pull up to ``count`` recent
        videos, then computes aggregate totals and identifies top-performing
        content. This powers the analytics/insights dashboard even without
        access to individual comment text.

        Returns::

            {
                "video_count": int,
                "total_likes": int,
                "total_comments": int,
                "total_shares": int,
                "total_views": int,
                "avg_likes": float,
                "avg_comments": float,
                "avg_shares": float,
                "avg_views": float,
                "top_by_views": {...} | None,
                "top_by_likes": {...} | None,
                "top_by_comments": {...} | None,
                "research_api_available": bool,
                "engagement_rate": float,   # (likes+comments+shares)/views
            }
        """
        posts = self.get_own_posts(access_token, count=min(count, 20))

        empty = {
            "video_count": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "total_views": 0,
            "avg_likes": 0.0,
            "avg_comments": 0.0,
            "avg_shares": 0.0,
            "avg_views": 0.0,
            "top_by_views": None,
            "top_by_likes": None,
            "top_by_comments": None,
            "research_api_available": TikTokProvider._research_api_available,
            "engagement_rate": 0.0,
        }

        if not posts:
            logger.debug("TikTok engagement summary: no posts found")
            return empty

        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_views = 0

        best_views = None
        best_likes = None
        best_comments = None

        for p in posts:
            m = p.get("metrics", {})
            likes = m.get("likes", 0)
            comments = m.get("comments", 0)
            shares = m.get("shares", 0)
            views = m.get("views", 0)

            total_likes += likes
            total_comments += comments
            total_shares += shares
            total_views += views

            summary_entry = {
                "id": p.get("id"),
                "text": p.get("text", ""),
                "url": p.get("url", ""),
                "created_at": p.get("created_at", ""),
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "views": views,
            }

            if best_views is None or views > best_views["views"]:
                best_views = summary_entry
            if best_likes is None or likes > best_likes["likes"]:
                best_likes = summary_entry
            if best_comments is None or comments > best_comments["comments"]:
                best_comments = summary_entry

        n = len(posts)
        total_interactions = total_likes + total_comments + total_shares
        engagement_rate = (
            round(total_interactions / total_views, 6)
            if total_views > 0 else 0.0
        )

        return {
            "video_count": n,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "total_views": total_views,
            "avg_likes": round(total_likes / n, 2),
            "avg_comments": round(total_comments / n, 2),
            "avg_shares": round(total_shares / n, 2),
            "avg_views": round(total_views / n, 2),
            "top_by_views": best_views,
            "top_by_likes": best_likes,
            "top_by_comments": best_comments,
            "research_api_available": TikTokProvider._research_api_available,
            "engagement_rate": engagement_rate,
        }

    # ── User / token management ──────────────────────────────────────────

    def get_user_info(self, access_token: str) -> dict:
        """Fetch current user profile info."""
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{TIKTOK_API_BASE}/user/info/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                params={
                    "fields": "open_id,union_id,avatar_url,"
                              "display_name,username,follower_count,"
                              "following_count,likes_count,video_count",
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("user", {})

    def get_account_insights(self, access_token: str, **kwargs) -> dict:
        """Fetch account-level insights from user info.

        TikTok doesn't have a separate insights API, but user info
        provides follower_count, following_count, likes_count, and
        video_count."""
        try:
            info = self.get_user_info(access_token)
            return {
                "followers": info.get("follower_count", 0),
                "following": info.get("following_count", 0),
                "total_likes": info.get("likes_count", 0),
                "total_videos": info.get("video_count", 0),
                "username": info.get("username", ""),
                "display_name": info.get("display_name", ""),
            }
        except Exception as e:
            logger.error("TikTok get_account_insights failed: %s", e)
            return {}

    def audit_profile(self, access_token: str, **kwargs) -> ProfileSnapshot:
        """Audit a TikTok account's profile completeness.

        Fetches user info and creator info. Creator info also reveals whether
        the account is in SELF_ONLY mode (unaudited API access) — when it is,
        surfaces that as a warning in fields_thin so the dashboard can alert
        the owner that posts are private until TikTok approves the app.
        """
        snap = ProfileSnapshot()
        try:
            info = self.get_user_info(access_token)
        except Exception as exc:
            snap.error = f"TikTok profile fetch failed: {exc}"
            return snap

        # Creator info for publish settings (privacy options available)
        creator_info = {}
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/post/publish/creator_info/query/",
                    headers=self._api_headers(access_token),
                )
                if resp.status_code == 200:
                    creator_info = resp.json().get("data", {})
        except Exception:
            pass

        field_map = {
            "display_name": info.get("display_name", "").strip(),
            "username": info.get("username", "").strip(),
            "avatar_url": info.get("avatar_url", "").strip(),
            "follower_count": str(info.get("follower_count", 0)),
            "bio_description": info.get("bio_description", "").strip(),
        }

        present = {k: v for k, v in field_map.items() if v and v != "0"}
        missing = [k for k, v in field_map.items() if not v or v == "0"]
        thin = []

        # Flag SELF_ONLY limitation as a thin field so UI can warn the owner.
        privacy_options = creator_info.get("privacy_level_options", [])
        if privacy_options and all(p == "SELF_ONLY" for p in privacy_options):
            thin.append("privacy_level")
            present["privacy_level"] = "SELF_ONLY — posts are private until TikTok audits your app"

        snap.fields_present = present
        snap.fields_missing = missing
        snap.fields_thin = thin
        snap.raw_profile = {**info, "creator_info": creator_info}
        total = len(field_map) + (1 if thin else 0)
        snap.completeness_score = int(round(len(present) / total * 100)) if total else 0
        return snap

    def validate_token(self, access_token: str) -> bool:
        """Check token validity with a lightweight user info call."""
        try:
            info = self.get_user_info(access_token)
            return bool(info.get("open_id"))
        except Exception:
            return False

    def revoke_token(self, access_token: str) -> bool:
        """Revoke a TikTok access token."""
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{TIKTOK_API_BASE}/oauth/revoke/",
                    data={
                        "client_key": self.client_key,
                        "client_secret": self.client_secret,
                        "token": access_token,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                return resp.status_code == 200
        except Exception:
            return False


# ── Auto-register ────────────────────────────────────────────────────────────
register_provider(TikTokProvider())
