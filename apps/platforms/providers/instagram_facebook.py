"""
Instagram / Facebook Provider (via Facebook Graph API).

Instagram posting uses the Facebook Graph API — Instagram accounts must be
connected through a Facebook Page. This provider handles both Facebook Pages
and Instagram Professional accounts.

Full capability matrix:
─────────────────────────────────────────────────────────────────────────────
FACEBOOK                              │ INSTAGRAM
─────────────────────────────────────────────────────────────────────────────
Connect via OAuth                     │ Connect IG Business via FB Page
List user's Pages                     │ Publish single image
Publish text/photo/video to Page      │ Publish carousel
Read post metrics                     │ Publish Reels (video)
Publish Facebook Reels (video_reels)  │
Read Page insights                    │ Publish Stories
Read comments on Page posts           │ Read post metrics (insights)
Reply to comments                     │ Read account insights
Read Page messages (inbox)            │ Read comments on posts
Reply to Page messages                │ Reply to comments
Schedule posts (via API)              │ Read DMs
                                      │ Reply to DMs
                                      │ Hashtag search
─────────────────────────────────────────────────────────────────────────────

Permissions required (enable in Meta Developer Portal):
  Facebook: pages_manage_metadata, pages_manage_posts, pages_read_engagement,
            read_insights, pages_manage_engagement, pages_messaging
  Instagram: instagram_content_publish, instagram_manage_insights,
             instagram_manage_comments, instagram_manage_messages

Auth method:
  - Facebook Login for Business (recommended): Uses config_id — permissions
    are bundled in a Login Configuration created in the Meta App Dashboard.
    Set FB_LOGIN_CONFIG_ID in your .env.
  - Classic Facebook Login (fallback): Uses scope parameter with comma-separated
    permission names. Works if config_id is not set.

Docs:
  https://developers.facebook.com/docs/pages-api/
  https://developers.facebook.com/docs/instagram-api/
  https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from django.conf import settings

from apps.platforms.providers.base import (
    BaseProvider, OAuthResult, PlatformAuthError, PostMetrics,
    ProfileSnapshot, ProfileUpdateResult, PublishResult,
)
from apps.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

# ── Graph API versioning ─────────────────────────────────────────────────────
FB_API_VERSION = "v25.0"
FB_AUTH_URL = f"https://www.facebook.com/{FB_API_VERSION}/dialog/oauth"
FB_TOKEN_URL = f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token"
FB_API_BASE = f"https://graph.facebook.com/{FB_API_VERSION}"
FB_REEL_UPLOAD_BASE = f"https://rupload.facebook.com/video-upload/{FB_API_VERSION}"


def _is_video_media_url(url: str) -> bool:
    if not url:
        return False
    path = url.lower().split("?")[0]
    return path.endswith((".mp4", ".mov", ".avi", ".webm", ".m4v"))


def _graph_api_error_text(response: httpx.Response, *, limit: int = 500) -> str:
    """Extract a readable error from a Graph API error response."""
    try:
        payload = response.json()
        err = payload.get("error")
        if isinstance(err, dict):
            parts = [str(err.get("message", "")).strip()]
            if err.get("error_user_msg"):
                parts.append(str(err["error_user_msg"]).strip())
            code = err.get("code")
            subcode = err.get("error_subcode")
            if code:
                parts.append(f"(code {code}{f'/{subcode}' if subcode else ''})")
            text = " — ".join(p for p in parts if p)
            if text:
                return text[:limit]
    except Exception:
        pass
    return (response.text or "")[:limit]


def _reel_url_from_media_list(media_urls: Optional[list[str]]) -> str:
    """Pick the first video URL from a media list (never treat images as reels)."""
    for url in media_urls or []:
        if _is_video_media_url(url):
            return url
    return ""


def refresh_facebook_page_tokens(user_access_token: str) -> list[dict]:
    """Re-fetch Page access tokens after a user token refresh."""
    if not user_access_token:
        return []
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            pages_resp = client.get(f"{FB_API_BASE}/me/accounts", params={
                "fields": "id,name,access_token,picture",
                "access_token": user_access_token,
            })
            pages_resp.raise_for_status()
            pages = pages_resp.json().get("data", [])
    except Exception as exc:
        logger.warning("Could not refresh Facebook page tokens: %s", exc)
        return []

    return [
        {
            "id": p["id"],
            "name": p.get("name", ""),
            "access_token": p.get("access_token", ""),
            "picture_url": p.get("picture", {}).get("data", {}).get("url", ""),
        }
        for p in pages
        if p.get("id") and p.get("access_token")
    ]

# ── Login Configuration ──────────────────────────────────────────────────────
# Facebook Login for Business uses config_id (permission bundle created in
# Meta App Dashboard → Facebook Login for Business → Configurations).
# If FB_LOGIN_CONFIG_ID is set, we use config_id instead of scope.
# If not set, we fall back to classic scope-based login.
FB_LOGIN_CONFIG_ID = getattr(settings, "FB_LOGIN_CONFIG_ID", "")

# ── Scopes (classic fallback) ────────────────────────────────────────────────
# Used only when FB_LOGIN_CONFIG_ID is not set (classic Facebook Login).
# In development mode, app admins/testers can use ALL of these without App
# Review. For production (public users), App Review is needed.
FB_SCOPES = ",".join([
    # Basic (always available)
    "email",
    "public_profile",
    # Facebook Pages (current valid names for Graph API v25.0)
    "pages_manage_metadata",
    "pages_manage_posts",
    "pages_read_engagement",
    "pages_manage_engagement",
    "pages_messaging",
    "read_insights",
    # Instagram (instagram_basic removed — deprecated in v21.0+)
    "instagram_content_publish",
    "instagram_manage_insights",
    "instagram_manage_comments",
    "instagram_manage_messages",
])

# Timeout for all HTTP calls (seconds)
HTTP_TIMEOUT = 30.0

# Instagram Container API — poll until media is processed before publish
IG_CONTAINER_POLL_INTERVAL = 3
IG_CONTAINER_MAX_POLLS = 40  # ~2 min for images; reels use longer loops inline


def _wait_for_ig_container(
    client: httpx.Client,
    token: str,
    container_id: str,
    *,
    max_polls: int = IG_CONTAINER_MAX_POLLS,
    poll_interval: float = IG_CONTAINER_POLL_INTERVAL,
) -> tuple[bool, str]:
    """
    Poll Instagram media container until status_code is FINISHED.

    Returns (ready, error_message). error_message is empty when ready=True.
    """
    status_code = "IN_PROGRESS"
    for attempt in range(max_polls):
        status_resp = client.get(f"{FB_API_BASE}/{container_id}", params={
            "fields": "status_code,status",
            "access_token": token,
        })
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status_code = status_data.get("status_code", "IN_PROGRESS")

        if status_code == "FINISHED":
            return True, ""
        if status_code == "ERROR":
            detail = status_data.get("status", "Media processing failed.")
            logger.error(
                "Instagram container %s ERROR after %d polls: %s",
                container_id, attempt + 1, detail,
            )
            return False, f"Instagram could not process media: {detail}"
        if status_code == "EXPIRED":
            return False, "Media container expired before publishing. Please try again."
        time.sleep(poll_interval)

    logger.warning(
        "Instagram container %s still '%s' after %d polls — proceeding to publish",
        container_id, status_code, max_polls,
    )
    return True, ""


def _validate_ig_https_urls(urls: list[str]) -> Optional[str]:
    """Return an error string if any URL is missing or not HTTPS (IG requirement)."""
    if not urls:
        return "Instagram requires at least one image URL."
    for url in urls:
        if not url or not str(url).startswith("https://"):
            return (
                "Instagram requires publicly accessible HTTPS image URLs. "
                "Re-save the post media or check storage/CDN settings."
            )
    return None


# ═════════════════════════════════════════════════════════════════════════════
# FACEBOOK PROVIDER
# ═════════════════════════════════════════════════════════════════════════════

class FacebookProvider(BaseProvider):
    """
    Facebook Pages provider — full capability.

    After OAuth, the user's managed Pages are stored in metadata["pages"].
    All posting / engagement operations require a page_id + page_access_token.
    """
    platform_name = "facebook"

    def __init__(self):
        self.app_id = getattr(settings, "FACEBOOK_APP_ID", "")
        self.app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "")

    # ── OAuth ────────────────────────────────────────────────────────────────

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        # Facebook Login for Business: use config_id (permission bundle)
        # Classic Facebook Login: use scope (comma-separated permissions)
        if FB_LOGIN_CONFIG_ID:
            params["config_id"] = FB_LOGIN_CONFIG_ID
        else:
            params["scope"] = FB_SCOPES
        return f"{FB_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            # 1. Exchange code → short-lived user token
            resp = client.get(FB_TOKEN_URL, params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            })
            resp.raise_for_status()
            short_token = resp.json()["access_token"]

            # 2. Exchange → long-lived user token (60 days)
            long_resp = client.get(FB_TOKEN_URL, params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_token,
            })
            long_resp.raise_for_status()
            long_data = long_resp.json()
            access_token = long_data.get("access_token", short_token)

            # 3. Get user profile
            me = client.get(f"{FB_API_BASE}/me", params={
                "fields": "id,name,picture",
                "access_token": access_token,
            })
            me.raise_for_status()
            user = me.json()

            # 4. Get managed Pages (page tokens never expire while user token is valid)
            pages = []
            try:
                pages_resp = client.get(f"{FB_API_BASE}/me/accounts", params={
                    "fields": "id,name,access_token,picture",
                    "access_token": access_token,
                })
                pages_resp.raise_for_status()
                pages = pages_resp.json().get("data", [])
            except Exception:
                logger.info("Could not fetch pages — pages_manage_metadata may not be granted yet")

        expires_at = None
        if "expires_in" in long_data:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=long_data["expires_in"])

        page_list = [
            {
                "id": p["id"],
                "name": p["name"],
                "access_token": p["access_token"],
                "picture_url": p.get("picture", {}).get("data", {}).get("url", ""),
            }
            for p in pages
        ]

        return OAuthResult(
            platform_user_id=user.get("id", ""),
            username=user.get("name", "").lower().replace(" ", ""),
            display_name=user.get("name", ""),
            avatar_url=user.get("picture", {}).get("data", {}).get("url", ""),
            access_token=access_token,
            refresh_token="",  # FB uses long-lived tokens, not refresh tokens
            token_expires_at=expires_at,
            token_scope=FB_SCOPES,
            metadata={
                "pages": page_list,
                # selected_page_id: which Page Kova publishes to.
                # Defaults to the first page. Users can change it via Settings → Platforms.
                # Preserved across reconnects by the OAuth callback view.
                "selected_page_id": page_list[0]["id"] if page_list else None,
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Extend a Facebook long-lived token for another ~60 days.

        Facebook doesn't use refresh tokens. Instead, you exchange a still-valid
        long-lived user token for a new one via the same fb_exchange_token grant.
        Must be called BEFORE the token expires.

        The ``refresh_token`` parameter is actually the current access_token
        (stored there by the refresh task for FB accounts).
        """
        current_token = refresh_token  # for FB, the task passes access_token here
        if not current_token:
            raise ValueError("No access token to extend")

        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.get(FB_TOKEN_URL, params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": current_token,
            })
            resp.raise_for_status()
            data = resp.json()

        expires_in = data.get("expires_in", 5184000)  # default 60 days
        return {
            "access_token": data["access_token"],
            "expires_in": expires_in,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        }

    # ── Publishing ───────────────────────────────────────────────────────────

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Publish to a Facebook Page.
        Required kwargs: page_id, page_access_token
        Optional kwargs: scheduled_publish_time, media_files
        """
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)
        scheduled_time = kwargs.get("scheduled_publish_time")
        media_files = kwargs.get("media_files")  # [(filename, bytes, content_type), ...]

        if not page_id:
            return PublishResult(success=False, error="page_id is required for Facebook posting")

        media_type = (kwargs.get("media_type") or "").upper()
        if media_type == "REELS":
            video_url = kwargs.get("video_url") or (media_urls[0] if media_urls else "")
            if not video_url:
                return PublishResult(success=False, error="video_url is required for Facebook Reels")
            return self.publish_reel(
                access_token, video_url, description=content, **kwargs,
            )
        if media_type == "VIDEO" or (
            media_urls and len(media_urls) == 1 and _is_video_media_url(media_urls[0])
        ):
            video_url = kwargs.get("video_url") or media_urls[0]
            return self.publish_video(
                access_token, video_url, description=content, **kwargs,
            )

        payload = {"message": content, "access_token": page_token}

        # Scheduling: publish at a future time (10 min − 6 months from now)
        if scheduled_time:
            payload["published"] = "false"
            payload["scheduled_publish_time"] = str(int(scheduled_time))

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                # ── Direct file upload (preferred: no public URL needed) ──
                if media_files and len(media_files) == 1:
                    fname, data, ctype = media_files[0]
                    logger.info("Facebook photo post to page %s (direct upload, %d bytes)", page_id, len(data))
                    resp = client.post(
                        f"{FB_API_BASE}/{page_id}/photos",
                        data=payload,
                        files={"source": (fname, data, ctype)},
                    )
                elif media_files and len(media_files) > 1:
                    # Multi-photo: upload each directly, then combine
                    photo_ids = []
                    for fname, data, ctype in media_files:
                        upload_resp = client.post(
                            f"{FB_API_BASE}/{page_id}/photos",
                            data={"published": "false", "access_token": page_token},
                            files={"source": (fname, data, ctype)},
                        )
                        upload_resp.raise_for_status()
                        photo_ids.append(upload_resp.json()["id"])
                    multi_payload = {"message": content, "access_token": page_token}
                    for i, pid in enumerate(photo_ids):
                        multi_payload[f"attached_media[{i}]"] = f'{{"media_fbid":"{pid}"}}'
                    resp = client.post(f"{FB_API_BASE}/{page_id}/feed", data=multi_payload)

                # ── URL-based upload (fallback: AI-generated images) ──────
                elif media_urls and len(media_urls) == 1:
                    image_url = media_urls[0]
                    if "localhost" in image_url or "127.0.0.1" in image_url:
                        logger.error("Facebook publish blocked: localhost image URL %s", image_url)
                        return PublishResult(success=False, error="Image URL is not publicly accessible (localhost)")
                    payload["url"] = image_url
                    logger.info("Facebook photo post to page %s with image: %s", page_id, image_url)
                    resp = client.post(f"{FB_API_BASE}/{page_id}/photos", data=payload)
                elif media_urls and len(media_urls) > 1:
                    photo_ids = []
                    for url in media_urls:
                        upload_resp = client.post(f"{FB_API_BASE}/{page_id}/photos", data={
                            "url": url,
                            "published": "false",
                            "access_token": page_token,
                        })
                        upload_resp.raise_for_status()
                        photo_ids.append(upload_resp.json()["id"])
                    multi_payload = {"message": content, "access_token": page_token}
                    for i, pid in enumerate(photo_ids):
                        multi_payload[f"attached_media[{i}]"] = f'{{"media_fbid":"{pid}"}}'
                    resp = client.post(f"{FB_API_BASE}/{page_id}/feed", data=multi_payload)
                else:
                    # Text-only post
                    resp = client.post(f"{FB_API_BASE}/{page_id}/feed", data=payload)

                resp.raise_for_status()
                post_id = resp.json().get("id", "")
                # Fetch canonical permalink — raw post IDs like "123_456" are not
                # valid Facebook URLs; Graph API returns the real link on request.
                try:
                    plink_resp = client.get(f"{FB_API_BASE}/{post_id}", params={
                        "fields": "permalink_url",
                        "access_token": page_token,
                    })
                    url = plink_resp.json().get("permalink_url",
                                               f"https://www.facebook.com/{post_id}")
                except Exception:
                    url = f"https://www.facebook.com/{post_id}"
                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    url=url,
                )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_text = _graph_api_error_text(e.response)
            logger.error("Facebook publish failed (HTTP %d): %s", status_code, error_text)
            if status_code in (429, 500, 502, 503, 504):
                raise
            return PublishResult(success=False, error=error_text)

    def publish_video(self, access_token: str, video_url: str,
                      description: str = "", **kwargs) -> PublishResult:
        """Publish a video to a Facebook Page."""
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)
        if not page_id:
            return PublishResult(success=False, error="page_id is required")

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(f"{FB_API_BASE}/{page_id}/videos", data={
                    "file_url": video_url,
                    "description": description,
                    "access_token": page_token,
                })
                resp.raise_for_status()
                video_id = resp.json().get("id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=video_id,
                    url=f"https://www.facebook.com/{video_id}",
                )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_text = _graph_api_error_text(e.response)
            logger.error("Facebook video publish failed (HTTP %d): %s", status_code, error_text)
            if status_code in (429, 500, 502, 503, 504):
                raise
            return PublishResult(success=False, error=error_text)

    def publish_reel(self, access_token: str, video_url: str,
                     description: str = "", **kwargs) -> PublishResult:
        """Publish a Reel to a Facebook Page via the video_reels API."""
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)
        if not page_id:
            return PublishResult(success=False, error="page_id is required")

        if "localhost" in video_url or "127.0.0.1" in video_url:
            return PublishResult(
                success=False,
                error="Video URL is not publicly accessible (localhost)",
            )

        try:
            with httpx.Client(timeout=180.0) as client:
                start_resp = client.post(
                    f"{FB_API_BASE}/{page_id}/video_reels",
                    data={"upload_phase": "start", "access_token": page_token},
                )
                start_resp.raise_for_status()
                start_data = start_resp.json()
                video_id = start_data.get("video_id")
                if not video_id:
                    return PublishResult(
                        success=False,
                        error=start_data.get("message", "Facebook Reels upload start failed"),
                    )

                upload_resp = client.post(
                    f"{FB_REEL_UPLOAD_BASE}/{video_id}",
                    headers={
                        "Authorization": f"OAuth {page_token}",
                        "file_url": video_url,
                    },
                )
                upload_resp.raise_for_status()

                finish_payload = {
                    "upload_phase": "finish",
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": description,
                    "access_token": page_token,
                }
                finish_resp = client.post(
                    f"{FB_API_BASE}/{page_id}/video_reels",
                    data=finish_payload,
                )
                finish_resp.raise_for_status()
                finish_data = finish_resp.json()
                post_id = finish_data.get("post_id") or video_id
                url = f"https://www.facebook.com/reel/{video_id}"
                try:
                    plink_resp = client.get(f"{FB_API_BASE}/{post_id}", params={
                        "fields": "permalink_url",
                        "access_token": page_token,
                    })
                    url = plink_resp.json().get("permalink_url") or url
                except Exception:
                    pass
                return PublishResult(
                    success=True,
                    platform_post_id=str(post_id),
                    url=url,
                    metadata={"video_id": video_id, "media_type": "reel"},
                )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_text = _graph_api_error_text(e.response)
            logger.error("Facebook Reel publish failed (HTTP %d): %s", status_code, error_text)
            if status_code in (429, 500, 502, 503, 504):
                raise
            return PublishResult(success=False, error=error_text)

    # ── Metrics & Insights ───────────────────────────────────────────────────

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """Fetch engagement metrics for a Page post. Requires pages_read_engagement."""
        likes = 0
        comments = 0
        shares = 0
        impressions = 0
        reach = 0
        clicks = 0

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                # Step 1: Basic engagement (likes, comments, shares)
                # Note: 'shares' field is unavailable on some post types;
                # try with it first, fall back without it.
                for _fields in (
                    "likes.summary(true),comments.summary(true),shares",
                    "likes.summary(true),comments.summary(true)",
                ):
                    resp = client.get(f"{FB_API_BASE}/{platform_post_id}", params={
                        "fields": _fields,
                        "access_token": access_token,
                    })
                    if resp.status_code == 200:
                        break
                resp.raise_for_status()
                data = resp.json()
                likes = data.get("likes", {}).get("summary", {}).get("total_count", 0)
                comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
                shares = data.get("shares", {}).get("count", 0)

                # Step 2: Post insights (impressions, reach, clicks) — may fail
                # on Reels, Stories, or shared posts. Try standard metrics first,
                # then fall back to the subset that works for all post types.
                _INSIGHT_METRIC_SETS = [
                    "post_impressions,post_impressions_unique,post_clicks",
                    "post_impressions,post_impressions_unique",  # clicks unsupported on some types
                ]
                insights_data = []
                for metric_set in _INSIGHT_METRIC_SETS:
                    try:
                        insights_resp = client.get(
                            f"{FB_API_BASE}/{platform_post_id}/insights",
                            params={
                                "metric": metric_set,
                                "access_token": access_token,
                            },
                        )
                        insights_resp.raise_for_status()
                        insights_data = insights_resp.json().get("data", [])
                        break  # success — stop trying
                    except httpx.HTTPStatusError:
                        continue  # try next metric set

                for insight in insights_data:
                    name = insight.get("name", "")
                    val = insight.get("values", [{}])[0].get("value", 0)
                    if name == "post_impressions":
                        impressions = val if isinstance(val, int) else 0
                    elif name == "post_impressions_unique":
                        reach = val if isinstance(val, int) else 0
                    elif name == "post_clicks":
                        clicks = val if isinstance(val, int) else 0

                if not insights_data:
                    logger.debug("Insights unavailable for post %s (unsupported post type)",
                                 platform_post_id)

        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            logger.error("Facebook metrics fetch failed: %s", error_text)
            # Re-raise permission errors so the circuit breaker in tasks can catch them
            if "pages_read_engagement" in error_text or "OAuthException" in error_text:
                raise RuntimeError(f"Facebook permission error: {error_text[:300]}")
            return PostMetrics()

        return PostMetrics(
            likes=likes,
            comments=comments,
            shares=shares,
            impressions=impressions,
            reach=reach,
            clicks=clicks,
        )

    def get_account_insights(self, access_token: str, **kwargs) -> dict:
        """
        Fetch Page-level insights. Requires read_insights.
        kwargs: page_id, page_access_token, period (day/week/month)
        """
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)
        period = kwargs.get("period", "day")
        if not page_id:
            return {"error": "page_id is required"}

        metrics = [
            "page_impressions",
            "page_impressions_unique",
            "page_engaged_users",
            "page_fan_adds",
            "page_fan_removes",
            "page_views_total",
            "page_post_engagements",
        ]
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{page_id}/insights", params={
                    "metric": ",".join(metrics),
                    "period": period,
                    "access_token": page_token,
                })
                resp.raise_for_status()
                result = {}
                for item in resp.json().get("data", []):
                    values = item.get("values", [])
                    result[item["name"]] = values[-1]["value"] if values else 0
                return result
        except httpx.HTTPStatusError as e:
            logger.error("Facebook page insights failed: %s", e.response.text)
            return {"error": e.response.text[:500]}

    # ── Engagement: Comments ─────────────────────────────────────────────────

    def get_comments(self, access_token: str, post_id: str, **kwargs) -> list[dict]:
        """Fetch comments on a Page post. Requires pages_manage_engagement."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{post_id}/comments", params={
                    "fields": "id,from{id,name},message,created_time",
                    "limit": kwargs.get("limit", 50),
                    "access_token": access_token,
                })
                resp.raise_for_status()
                return [
                    {
                        "id": c["id"],
                        "author_id": c.get("from", {}).get("id", ""),
                        "author_name": c.get("from", {}).get("name", ""),
                        "text": c.get("message", ""),
                        "created_at": c.get("created_time", ""),
                    }
                    for c in resp.json().get("data", [])
                ]
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error("Facebook get comments failed for post %s: %s", post_id, error_body)
            # "does not exist" = deleted/unavailable post — NOT an auth error
            if "does not exist" in error_body:
                logger.info("Post %s no longer exists on Facebook — skipping", post_id)
                return []
            # Detect genuine token/permission errors — caller should mark account for reauth
            if e.response.status_code == 400 and ("OAuthException" in error_body or "code\":190" in error_body):
                raise PlatformAuthError(f"Facebook token/permission error: {error_body[:300]}") from e
            return []

    def post_comment(self, page_token: str = "", post_id: str = "",
                     message: str = "", **kwargs) -> dict:
        """Post a comment on a Page post.

        Originally written for the first-comment link-in-comments strategy.
        Also used by the Engage Agent (v2 May 2026) to auto-reply to
        comments on Pages. Accepts both ``page_token`` (canonical) and
        ``access_token`` (engage_agent's call site) as the token kwarg.
        """
        token = page_token or kwargs.get("access_token", "")
        account = kwargs.get("account")
        if account is not None:
            meta = account.metadata or {}
            pages = meta.get("pages", [])
            if pages:
                selected_id = meta.get("selected_page_id")
                selected_page = (
                    next((p for p in pages if p["id"] == selected_id), None)
                    if selected_id else None
                ) or pages[0]
                token = selected_page.get("access_token", token or account.access_token)
            elif not token:
                token = account.access_token
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/{post_id}/comments", data={
                    "message": message,
                    "access_token": token,
                })
                resp.raise_for_status()
                return {"id": resp.json().get("id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Facebook comment post failed on %s: %s", post_id, e.response.text)
            return {"error": e.response.text[:300], "success": False}

    def delete_comment(self, access_token: str = "", comment_id: str = "",
                       **kwargs) -> dict:
        """Delete a comment by its FB comment ID.

        Used by the Engage Agent undo flow (W2 May 2026) — the user has
        5 minutes after an AI auto-send to retract. Returns
        ``{"success": True}`` on a 200/204 and ``{"success": False, "error": ...}``
        otherwise. Idempotent on the caller's side — re-calling on an
        already-deleted comment surfaces the API's 404.
        """
        token = access_token or kwargs.get("page_token", "")
        account = kwargs.get("account")
        if account is not None and not token:
            token = account.access_token
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.delete(
                    f"{FB_API_BASE}/{comment_id}",
                    params={"access_token": token},
                )
                resp.raise_for_status()
                return {"success": True}
        except httpx.HTTPStatusError as e:
            logger.warning("Facebook delete_comment failed on %s: %s", comment_id, e.response.text[:200])
            return {"error": e.response.text[:300], "success": False}

    def reply_to_comment(self, access_token: str, comment_id: str,
                         message: str, **kwargs) -> dict:
        """Reply to a comment on a Page post. Requires pages_manage_engagement."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/{comment_id}/comments", data={
                    "message": message,
                    "access_token": access_token,
                })
                resp.raise_for_status()
                return {"id": resp.json().get("id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Facebook reply to comment failed: %s", e.response.text)
            return {"error": e.response.text[:500], "success": False}

    # ── Engagement: Messages (Page Inbox) ────────────────────────────────────

    def get_messages(self, access_token: str, **kwargs) -> list[dict]:
        """
        Fetch Page conversations. Requires pages_messaging.
        kwargs: page_id, page_access_token
        """
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)
        if not page_id:
            return []

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{page_id}/conversations", params={
                    "fields": "id,participants,updated_time,messages.limit(5)"
                              "{id,from,to,message,created_time}",
                    "limit": kwargs.get("limit", 20),
                    "access_token": page_token,
                })
                resp.raise_for_status()
                conversations = []
                for conv in resp.json().get("data", []):
                    messages = []
                    for msg in conv.get("messages", {}).get("data", []):
                        messages.append({
                            "id": msg.get("id", ""),
                            "sender_id": msg.get("from", {}).get("id", ""),
                            "sender_name": msg.get("from", {}).get("name", ""),
                            "text": msg.get("message", ""),
                            "created_at": msg.get("created_time", ""),
                        })
                    conversations.append({
                        "conversation_id": conv["id"],
                        "updated_at": conv.get("updated_time", ""),
                        "participants": [
                            p.get("name", "") for p in conv.get("participants", {}).get("data", [])
                        ],
                        "messages": messages,
                    })
                return conversations
        except httpx.HTTPStatusError as e:
            logger.error("Facebook get messages failed: %s", e.response.text)
            return []

    def send_message(self, access_token: str, recipient_id: str,
                     message: str, **kwargs) -> dict:
        """
        Send a message from a Page. Requires pages_messaging.
        kwargs: page_id, page_access_token
        """
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)
        if not page_id:
            return {"error": "page_id is required for Facebook Messenger send", "success": False}
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/{page_id}/messages", json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": message},
                    "access_token": page_token,
                })
                resp.raise_for_status()
                return {"id": resp.json().get("message_id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Facebook send message failed: %s", e.response.text)
            return {"error": e.response.text[:500], "success": False}

    # ── User Info / Token Validation ─────────────────────────────────────────

    def get_user_info(self, access_token: str) -> dict:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.get(f"{FB_API_BASE}/me", params={
                "fields": "id,name,picture",
                "access_token": access_token,
            })
            resp.raise_for_status()
            return resp.json()

    def validate_token(self, access_token: str) -> bool:
        """Validate token using Meta's debug endpoint."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/debug_token", params={
                    "input_token": access_token,
                    "access_token": f"{self.app_id}|{self.app_secret}",
                })
                resp.raise_for_status()
                return resp.json().get("data", {}).get("is_valid", False)
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────────────
    # PROFILE AUDIT — Facebook Page
    # ──────────────────────────────────────────────────────────────────
    # Fields we audit (FB Page Graph API field names). Weights sum to 100.
    # See https://developers.facebook.com/docs/graph-api/reference/page
    _FB_AUDIT_FIELDS = {
        "about": 18,
        "description": 12,
        "phone": 10,
        "emails": 8,
        "single_line_address": 10,
        "website": 12,
        "hours": 10,
        "category": 8,
        "picture": 7,
        "cover": 5,
    }

    # If a string field's stripped length is below this we consider it "thin".
    _FB_THIN_THRESHOLDS = {
        "about": 30,
        "description": 80,
        "website": 8,
    }

    def audit_profile(self, access_token: str, **kwargs) -> ProfileSnapshot:
        """Audit a Facebook Page's profile completeness.

        Requires a Page-scoped access_token (NOT the user token) and the
        page_id is implicit in the token. We fetch all field values, score
        completeness, identify gaps and 'thin' values."""
        snap = ProfileSnapshot()

        page_id = kwargs.get("page_id") or kwargs.get("platform_user_id") or "me"
        fields_param = ",".join(self._FB_AUDIT_FIELDS.keys())
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(
                    f"{FB_API_BASE}/{page_id}",
                    params={"fields": fields_param, "access_token": access_token},
                )
                if resp.status_code in (401, 403):
                    raise PlatformAuthError(f"Facebook auth error: {resp.text[:200]}")
                resp.raise_for_status()
                data = resp.json()
        except PlatformAuthError:
            raise
        except Exception as exc:
            snap.error = f"Facebook audit failed: {exc}"
            return snap

        snap.raw_profile = self._truncate_raw(data)

        present = {}
        missing = []
        thin = []
        score = 0
        total_weight = sum(self._FB_AUDIT_FIELDS.values())

        for field_name, weight in self._FB_AUDIT_FIELDS.items():
            value = data.get(field_name)
            normalized = self._fb_normalize_field(field_name, value)
            if normalized:
                present[field_name] = normalized
                # Thin check
                threshold = self._FB_THIN_THRESHOLDS.get(field_name)
                if threshold and isinstance(normalized, str) and len(normalized.strip()) < threshold:
                    thin.append(field_name)
                    score += weight * 0.5  # half-credit for thin
                else:
                    score += weight
            else:
                missing.append(field_name)

        snap.fields_present = present
        snap.fields_missing = missing
        snap.fields_thin = thin
        snap.completeness_score = int(round((score / total_weight) * 100)) if total_weight else 0
        return snap

    @staticmethod
    def _fb_normalize_field(field_name: str, value) -> str:
        """Coerce raw Graph API values into displayable strings.
        Returns '' for empty / missing values."""
        # Treat None, empty string, empty dict, empty list all as missing
        if value is None or value == "" or value == {} or value == []:
            return ""
        # Default-FB picture comes back as {"data": {"url": "..."}} and is
        # 'silhouette' for un-customized pages. We treat absence of a real
        # photo as missing.
        if field_name == "picture":
            data = (value or {}).get("data", {}) if isinstance(value, dict) else {}
            url = data.get("url", "")
            if not url or "silhouette" in url:
                return ""
            return url
        if field_name == "cover":
            source = (value or {}).get("source", "") if isinstance(value, dict) else ""
            return source or ""
        if field_name == "emails":
            if isinstance(value, list):
                value = ", ".join(value)
            return str(value or "")
        if field_name == "hours" and isinstance(value, dict):
            # Hours is a complex dict like {"mon_1_open": "09:00", ...}
            return "set" if value else ""
        return str(value).strip()

    @staticmethod
    def _truncate_raw(data: dict, max_chars: int = 4000) -> dict:
        """Trim raw profile dump to avoid huge JSON rows."""
        try:
            import json
            s = json.dumps(data, default=str)
            if len(s) <= max_chars:
                return data
            return {"_truncated": True, "_preview": s[:max_chars]}
        except Exception:
            return {"_unserializable": True}

    # ──────────────────────────────────────────────────────────────────
    # PROFILE UPDATE — Facebook Page
    # ──────────────────────────────────────────────────────────────────
    # Graph API field-name mapping for updates. Most fields update via
    # POST /{page-id} with field=value in the body. Some (picture/cover)
    # need separate endpoints — those are handled with _FB_UPDATE_HANDLERS.
    _FB_WRITABLE_FIELDS = {
        "about",
        "description",
        "phone",
        "emails",
        "website",
        "hours",
        "single_line_address",
        "category_list",
    }

    def update_profile(
        self, access_token: str, updates: dict, **kwargs,
    ) -> ProfileUpdateResult:
        """Apply field updates to a Facebook Page. One field per call —
        Graph API accepts multiple in one POST but failures are easier to
        debug field-by-field, and we only ever apply one suggestion at a time."""
        if not updates:
            return ProfileUpdateResult(success=False, error="No updates provided.")

        # We apply ONE field per call; callers iterate
        field_name, new_value = next(iter(updates.items()))
        page_id = kwargs.get("page_id") or kwargs.get("platform_user_id") or "me"

        if field_name not in self._FB_WRITABLE_FIELDS:
            return ProfileUpdateResult(
                success=False, field_name=field_name,
                error=f"Field '{field_name}' is not writable via API.",
            )

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(
                    f"{FB_API_BASE}/{page_id}",
                    data={field_name: new_value, "access_token": access_token},
                )
                if resp.status_code in (401, 403):
                    raise PlatformAuthError(f"Facebook auth error: {resp.text[:200]}")
                if not resp.is_success:
                    return ProfileUpdateResult(
                        success=False, field_name=field_name,
                        error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                        api_response=self._truncate_raw(self._safe_json(resp)),
                    )
                body = self._safe_json(resp)
        except PlatformAuthError:
            raise
        except Exception as exc:
            return ProfileUpdateResult(
                success=False, field_name=field_name,
                error=f"Facebook update failed: {exc}",
            )

        # Re-fetch the field to confirm what the platform actually stored
        # (FB may trim / normalize). Use the audit method to keep parity.
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(
                    f"{FB_API_BASE}/{page_id}",
                    params={"fields": field_name, "access_token": access_token},
                )
                resp.raise_for_status()
                applied = self._fb_normalize_field(field_name, resp.json().get(field_name))
        except Exception:
            applied = str(new_value)

        return ProfileUpdateResult(
            success=True, field_name=field_name,
            applied_value=applied, api_response=body,
        )

    @staticmethod
    def _safe_json(resp) -> dict:
        try:
            return resp.json()
        except Exception:
            return {"text": resp.text[:500]}


# ═════════════════════════════════════════════════════════════════════════════
# INSTAGRAM PROVIDER
# ═════════════════════════════════════════════════════════════════════════════

class InstagramProvider(BaseProvider):
    """
    Instagram Professional Account provider (via Facebook Graph API).

    Instagram accounts must be linked to a Facebook Page. The IG user ID and
    page token are stored in metadata after OAuth.

    Supports: image posts, carousels, Reels, Stories, comments, DMs, insights.
    """
    platform_name = "instagram"

    def __init__(self):
        self.app_id = getattr(settings, "FACEBOOK_APP_ID", "")
        self.app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "")

    # ── OAuth ────────────────────────────────────────────────────────────────

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        # Facebook Login for Business: use config_id (permission bundle)
        # Classic Facebook Login: use scope (comma-separated permissions)
        if FB_LOGIN_CONFIG_ID:
            params["config_id"] = FB_LOGIN_CONFIG_ID
        else:
            params["scope"] = FB_SCOPES
        return f"{FB_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            # 1. Exchange code → short-lived token
            resp = client.get(FB_TOKEN_URL, params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            })
            resp.raise_for_status()
            access_token = resp.json()["access_token"]

            # 2. Exchange → long-lived token (60 days)
            long_resp = client.get(FB_TOKEN_URL, params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": access_token,
            })
            long_resp.raise_for_status()
            long_data = long_resp.json()
            access_token = long_data.get("access_token", access_token)

            # 3. Get user's Pages
            pages_resp = client.get(f"{FB_API_BASE}/me/accounts", params={
                "fields": "id,name,access_token",
                "access_token": access_token,
            })
            pages_resp.raise_for_status()
            pages = pages_resp.json().get("data", [])

            # 4. Find Instagram Business Account linked to a Page
            ig_account = None
            page_id = ""
            page_token = ""
            for page in pages:
                ig_resp = client.get(f"{FB_API_BASE}/{page['id']}", params={
                    "fields": "instagram_business_account",
                    "access_token": page["access_token"],
                })
                ig_resp.raise_for_status()
                ig_data = ig_resp.json().get("instagram_business_account")
                if ig_data:
                    ig_account = ig_data
                    page_id = page["id"]
                    page_token = page["access_token"]
                    break

            if not ig_account:
                raise ValueError(
                    "No Instagram Business/Creator Account found linked to your Facebook Pages. "
                    "Make sure your Instagram account is converted to Professional and linked to a Facebook Page."
                )

            ig_id = ig_account["id"]

            # 5. Fetch IG profile
            ig_profile = client.get(f"{FB_API_BASE}/{ig_id}", params={
                "fields": "id,username,name,profile_picture_url,followers_count,media_count",
                "access_token": page_token,
            })
            ig_profile.raise_for_status()
            profile = ig_profile.json()

        expires_at = None
        if "expires_in" in long_data:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=long_data["expires_in"])

        return OAuthResult(
            platform_user_id=ig_id,
            username=profile.get("username", ""),
            display_name=profile.get("name", profile.get("username", "")),
            avatar_url=profile.get("profile_picture_url", ""),
            access_token=page_token,  # IG API calls use the page token
            refresh_token="",
            token_expires_at=expires_at,
            token_scope=FB_SCOPES,
            metadata={
                "ig_business_id": ig_id,
                "page_id": page_id,
                "page_access_token": page_token,
                "user_access_token": access_token,
                "followers_count": profile.get("followers_count", 0),
                "media_count": profile.get("media_count", 0),
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Extend an Instagram long-lived token for another ~60 days.

        Instagram tokens (via Facebook Graph API) use the same fb_exchange_token
        mechanism as Facebook long-lived tokens. Must be called BEFORE expiry.
        The ``refresh_token`` param is the current access_token (page token).
        """
        current_token = refresh_token  # for IG via FB, the task passes access_token here
        if not current_token:
            raise ValueError("No access token to extend")

        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.get(FB_TOKEN_URL, params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": current_token,
            })
            resp.raise_for_status()
            data = resp.json()

        expires_in = data.get("expires_in", 5184000)  # default 60 days
        return {
            "access_token": data["access_token"],
            "expires_in": expires_in,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        }

    # ── Publishing ───────────────────────────────────────────────────────────

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Publish to Instagram. Requires instagram_content_publish.

        kwargs:
            ig_user_id: Instagram Business Account ID (from metadata)
            media_type: "IMAGE" (default), "CAROUSEL", "REELS", "STORIES"
            video_url: URL of video for Reels
        """
        ig_user_id = kwargs.get("ig_user_id", "")
        media_type = kwargs.get("media_type", "IMAGE").upper()
        token = kwargs.get("page_access_token") or access_token

        if not ig_user_id:
            return PublishResult(success=False, error="ig_user_id is required")

        try:
            with httpx.Client(timeout=120.0) as client:
                if media_type == "CAROUSEL" and media_urls and len(media_urls) > 1:
                    return self._publish_carousel(client, token, ig_user_id, content, media_urls)
                elif media_type == "REELS":
                    video_url = kwargs.get("video_url") or _reel_url_from_media_list(media_urls)
                    return self._publish_reels(client, token, ig_user_id, content, video_url)
                elif media_type == "STORIES":
                    return self._publish_story(client, token, ig_user_id, media_urls)
                elif media_urls:
                    return self._publish_single_image(client, token, ig_user_id, content, media_urls[0])
                else:
                    return PublishResult(
                        success=False,
                        error="Instagram requires media (image or video) for publishing.",
                    )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_text = _graph_api_error_text(e.response)
            logger.error("Instagram publish failed (HTTP %d): %s", status_code, error_text)
            if status_code in (429, 500, 502, 503, 504):
                raise
            return PublishResult(success=False, error=error_text)

    def _fetch_ig_permalink(self, client: httpx.Client, token: str,
                            post_id: str) -> str:
        """Fetch the canonical permalink for a published IG media object.

        The raw Graph API media ID is not a valid Instagram URL — we must call
        `GET /{post_id}?fields=permalink` to get the real shortcode-based URL.
        Falls back to a best-effort URL on any error.
        """
        try:
            resp = client.get(f"{FB_API_BASE}/{post_id}", params={
                "fields": "permalink",
                "access_token": token,
            })
            permalink = resp.json().get("permalink", "")
            if permalink:
                return permalink
        except Exception:
            pass
        return f"https://www.instagram.com/p/{post_id}/"

    def _publish_single_image(self, client: httpx.Client, token: str,
                              ig_id: str, caption: str, image_url: str) -> PublishResult:
        """Single image post."""
        url_err = _validate_ig_https_urls([image_url])
        if url_err:
            return PublishResult(success=False, error=url_err)

        container = client.post(f"{FB_API_BASE}/{ig_id}/media", data={
            "image_url": image_url,
            "caption": caption,
            "access_token": token,
        })
        container.raise_for_status()
        container_id = container.json()["id"]

        ready, err = _wait_for_ig_container(client, token, container_id)
        if not ready:
            return PublishResult(success=False, error=err)

        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        url = self._fetch_ig_permalink(client, token, post_id)
        return PublishResult(success=True, platform_post_id=post_id, url=url)

    def _publish_carousel(self, client: httpx.Client, token: str,
                          ig_id: str, caption: str, image_urls: list[str]) -> PublishResult:
        """Carousel post (2-10 images) with parallel container polling."""
        slides = image_urls[:10]
        if len(slides) < 2:
            return PublishResult(
                success=False,
                error="Instagram carousels need at least 2 images.",
            )
        url_err = _validate_ig_https_urls(slides)
        if url_err:
            return PublishResult(success=False, error=url_err)

        # Phase 1: Create ALL child containers without waiting
        child_ids = []
        for url in slides:
            child = client.post(f"{FB_API_BASE}/{ig_id}/media", data={
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": token,
            })
            child.raise_for_status()
            child_ids.append(child.json()["id"])

        # Phase 2: Poll ALL children in rounds (they process in parallel on Meta's side)
        pending = set(range(len(child_ids)))
        for poll_round in range(IG_CONTAINER_MAX_POLLS):
            if not pending:
                break
            time.sleep(IG_CONTAINER_POLL_INTERVAL)
            still_pending = set()
            for idx in pending:
                cid = child_ids[idx]
                status_resp = client.get(f"{FB_API_BASE}/{cid}", params={
                    "fields": "status_code,status",
                    "access_token": token,
                })
                status_resp.raise_for_status()
                status_data = status_resp.json()
                sc = status_data.get("status_code", "IN_PROGRESS")
                if sc == "FINISHED":
                    continue
                elif sc == "ERROR":
                    detail = status_data.get("status", "Image processing failed.")
                    logger.error("IG carousel child %s ERROR: %s", cid, detail)
                    return PublishResult(
                        success=False,
                        error=f"Instagram could not process slide {idx+1}: {detail}",
                    )
                elif sc == "EXPIRED":
                    return PublishResult(
                        success=False,
                        error=f"Carousel slide {idx+1} expired. Please retry.",
                    )
                else:
                    still_pending.add(idx)
            pending = still_pending

        if pending:
            logger.warning(
                "IG carousel: %d/%d children still not FINISHED after %d polls — proceeding",
                len(pending), len(child_ids), IG_CONTAINER_MAX_POLLS,
            )

        # Phase 3: Create parent carousel container
        carousel_data = {
            "media_type": "CAROUSEL",
            "caption": caption,
            "access_token": token,
        }
        for i, cid in enumerate(child_ids):
            carousel_data[f"children[{i}]"] = cid

        carousel = client.post(f"{FB_API_BASE}/{ig_id}/media", data=carousel_data)
        carousel.raise_for_status()
        carousel_id = carousel.json()["id"]

        # Phase 4: Poll parent container
        ready, err = _wait_for_ig_container(client, token, carousel_id, max_polls=20)
        if not ready:
            return PublishResult(success=False, error=err)

        # Phase 5: Publish
        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": carousel_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        url = self._fetch_ig_permalink(client, token, post_id)
        return PublishResult(success=True, platform_post_id=post_id, url=url)

    def _publish_reels(self, client: httpx.Client, token: str,
                       ig_id: str, caption: str, video_url: str) -> PublishResult:
        """Publish a Reel."""
        if not video_url:
            return PublishResult(success=False, error="video_url is required for Reels")
        if not str(video_url).startswith("https://"):
            return PublishResult(
                success=False,
                error=(
                    "Instagram Reels require a public HTTPS video URL. "
                    "Re-compose the reel or check media storage settings."
                ),
            )

        container = client.post(f"{FB_API_BASE}/{ig_id}/media", data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        })
        container.raise_for_status()
        container_id = container.json()["id"]

        # Poll until video is processed (max ~3 minutes: 60 polls × 3s).
        # Instagram status_code values: IN_PROGRESS → FINISHED | ERROR | EXPIRED
        status_code = "IN_PROGRESS"
        for attempt in range(60):
            status_resp = client.get(f"{FB_API_BASE}/{container_id}", params={
                "fields": "status_code,status",
                "access_token": token,
            })
            status_resp.raise_for_status()
            status_data = status_resp.json()
            status_code = status_data.get("status_code", "IN_PROGRESS")

            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                error_detail = status_data.get("status", "Video processing failed.")
                logger.error(
                    "Instagram Reel container %s ERROR after %d polls: %s",
                    container_id, attempt + 1, error_detail,
                )
                return PublishResult(
                    success=False,
                    error=(
                        f"Instagram could not process your video: {error_detail}. "
                        "Check: H.264/AAC codec, 9:16 ratio, under 1GB, MP4 or MOV format."
                    ),
                )
            if status_code == "EXPIRED":
                return PublishResult(
                    success=False,
                    error="Reel container expired before publishing. Please try again.",
                )
            time.sleep(3)
        else:
            # Loop exhausted (~3 min) without FINISHED — attempt publish anyway.
            # Very long videos (>10 min) or slow Instagram infra can exceed this.
            logger.warning(
                "Reel container %s still '%s' after 60 polls — attempting publish",
                container_id, status_code,
            )

        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        url = self._fetch_ig_permalink(client, token, post_id)
        return PublishResult(success=True, platform_post_id=post_id, url=url)

    def _publish_story(self, client: httpx.Client, token: str,
                       ig_id: str, media_urls: Optional[list[str]]) -> PublishResult:
        """Publish a Story (image or video)."""
        if not media_urls:
            return PublishResult(success=False, error="Media URL required for Stories")

        media_url = media_urls[0]
        is_video = any(media_url.lower().endswith(ext) for ext in [".mp4", ".mov", ".avi"])

        data = {"media_type": "STORIES", "access_token": token}
        if is_video:
            data["video_url"] = media_url
        else:
            data["image_url"] = media_url

        container = client.post(f"{FB_API_BASE}/{ig_id}/media", data=data)
        container.raise_for_status()
        container_id = container.json()["id"]

        if is_video:
            status_code = "IN_PROGRESS"
            for attempt in range(30):
                status_resp = client.get(f"{FB_API_BASE}/{container_id}", params={
                    "fields": "status_code,status", "access_token": token,
                })
                status_resp.raise_for_status()
                status_data = status_resp.json()
                status_code = status_data.get("status_code", "IN_PROGRESS")

                if status_code == "FINISHED":
                    break
                if status_code == "ERROR":
                    error_detail = status_data.get("status", "Video processing failed.")
                    logger.error(
                        "Instagram Story container %s ERROR after %d polls: %s",
                        container_id, attempt + 1, error_detail,
                    )
                    return PublishResult(
                        success=False,
                        error=(
                            f"Instagram could not process your Story video: {error_detail}. "
                            "Check video format (MP4/MOV, H.264, AAC audio)."
                        ),
                    )
                if status_code == "EXPIRED":
                    return PublishResult(
                        success=False,
                        error="Story container expired before publishing. Please try again.",
                    )
                time.sleep(2)

        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        return PublishResult(success=True, platform_post_id=post_id)

    # ── Metrics & Insights ───────────────────────────────────────────────────

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """Fetch post-level insights. Requires instagram_manage_insights."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{platform_post_id}/insights", params={
                    "metric": "impressions,reach,likes,comments,shares,saved",
                    "access_token": access_token,
                })
                resp.raise_for_status()
                metrics = {
                    m["name"]: m["values"][0]["value"]
                    for m in resp.json().get("data", [])
                }
                return PostMetrics(
                    likes=metrics.get("likes", 0),
                    comments=metrics.get("comments", 0),
                    shares=metrics.get("shares", 0),
                    impressions=metrics.get("impressions", 0),
                    reach=metrics.get("reach", 0),
                    saves=metrics.get("saved", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Instagram metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    def get_account_insights(self, access_token: str, **kwargs) -> dict:
        """
        Fetch account-level insights. Requires instagram_manage_insights.
        kwargs: ig_user_id, period (day/week/month)
        """
        ig_user_id = kwargs.get("ig_user_id", "")
        period = kwargs.get("period", "day")
        if not ig_user_id:
            return {"error": "ig_user_id is required"}

        metrics = [
            "impressions",
            "reach",
            "follower_count",
            "profile_views",
            "website_clicks",
        ]
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{ig_user_id}/insights", params={
                    "metric": ",".join(metrics),
                    "period": period,
                    "access_token": access_token,
                })
                resp.raise_for_status()
                result = {}
                for item in resp.json().get("data", []):
                    values = item.get("values", [])
                    result[item["name"]] = values[-1]["value"] if values else 0
                return result
        except httpx.HTTPStatusError as e:
            logger.error("Instagram account insights failed: %s", e.response.text)
            return {"error": e.response.text[:500]}

    # ── Engagement: Comments ─────────────────────────────────────────────────

    def get_comments(self, access_token: str, post_id: str, **kwargs) -> list[dict]:
        """Fetch comments on an IG post. Requires instagram_manage_comments."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{post_id}/comments", params={
                    "fields": "id,from{id,username},text,timestamp",
                    "limit": kwargs.get("limit", 50),
                    "access_token": access_token,
                })
                resp.raise_for_status()
                return [
                    {
                        "id": c["id"],
                        "author_id": c.get("from", {}).get("id", ""),
                        "author_name": c.get("from", {}).get("username", ""),
                        "text": c.get("text", ""),
                        "created_at": c.get("timestamp", ""),
                    }
                    for c in resp.json().get("data", [])
                ]
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error("Instagram get comments failed for post %s: %s", post_id, error_body)
            if "does not exist" in error_body:
                logger.info("Post %s no longer exists on Instagram — skipping", post_id)
                return []
            if e.response.status_code == 400 and ("OAuthException" in error_body or "code\":190" in error_body):
                raise PlatformAuthError(f"Instagram token/permission error: {error_body[:300]}") from e
            return []

    def post_comment(self, page_token: str = "", post_id: str = "",
                     message: str = "", **kwargs) -> dict:
        """
        Post a first comment on an IG post immediately after publishing.

        Used for save-prompts and link-in-bio CTAs — the first comment appears
        right below the caption and gets high visibility from engaged readers.
        Note: unlike Facebook, links in IG comments are also not clickable,
        so this is best used for text CTAs ('💾 Save this!', 'Link in bio 👆').
        """
        token = page_token or kwargs.get("access_token", "")
        account = kwargs.get("account")
        if account is not None and not token:
            token = account.access_token
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/{post_id}/comments", data={
                    "message": message,
                    "access_token": token,
                })
                resp.raise_for_status()
                return {"id": resp.json().get("id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Instagram comment post failed on %s: %s", post_id, e.response.text)
            return {"error": e.response.text[:300], "success": False}

    def delete_comment(self, access_token: str = "", comment_id: str = "",
                       **kwargs) -> dict:
        """Delete an Instagram comment by ID (Engage Agent undo, W2 May 2026)."""
        token = access_token or kwargs.get("page_token", "")
        account = kwargs.get("account")
        if account is not None and not token:
            token = account.access_token
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.delete(
                    f"{FB_API_BASE}/{comment_id}",
                    params={"access_token": token},
                )
                resp.raise_for_status()
                return {"success": True}
        except httpx.HTTPStatusError as e:
            logger.warning("Instagram delete_comment failed on %s: %s", comment_id, e.response.text[:200])
            return {"error": e.response.text[:300], "success": False}

    def reply_to_comment(self, access_token: str, comment_id: str,
                         message: str, **kwargs) -> dict:
        """Reply to a comment on an IG post. Requires instagram_manage_comments."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/{comment_id}/replies", data={
                    "message": message,
                    "access_token": access_token,
                })
                resp.raise_for_status()
                return {"id": resp.json().get("id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Instagram reply to comment failed: %s", e.response.text)
            return {"error": e.response.text[:500], "success": False}

    # ── Engagement: Direct Messages ──────────────────────────────────────────

    def get_messages(self, access_token: str, **kwargs) -> list[dict]:
        """
        Fetch IG Direct conversations. Requires instagram_manage_messages.
        kwargs: ig_user_id
        """
        ig_user_id = kwargs.get("ig_user_id", "")
        if not ig_user_id:
            return []

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/{ig_user_id}/conversations", params={
                    "platform": "instagram",
                    "fields": "id,participants,updated_time,messages.limit(5)"
                              "{id,from,to,message,created_time}",
                    "limit": kwargs.get("limit", 20),
                    "access_token": access_token,
                })
                resp.raise_for_status()
                conversations = []
                for conv in resp.json().get("data", []):
                    messages = []
                    for msg in conv.get("messages", {}).get("data", []):
                        messages.append({
                            "id": msg.get("id", ""),
                            "sender_id": msg.get("from", {}).get("id", ""),
                            "sender_name": msg.get("from", {}).get("name", ""),
                            "text": msg.get("message", ""),
                            "created_at": msg.get("created_time", ""),
                        })
                    conversations.append({
                        "conversation_id": conv["id"],
                        "updated_at": conv.get("updated_time", ""),
                        "messages": messages,
                    })
                return conversations
        except httpx.HTTPStatusError as e:
            logger.error("Instagram get messages failed: %s", e.response.text)
            return []

    def send_message(self, access_token: str, recipient_id: str,
                     message: str, **kwargs) -> dict:
        """
        Send an IG Direct message. Requires instagram_manage_messages.
        kwargs: ig_user_id
        """
        ig_user_id = kwargs.get("ig_user_id", "")
        if not ig_user_id:
            return {"error": "ig_user_id is required", "success": False}

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/{ig_user_id}/messages", json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": message},
                    "access_token": access_token,
                })
                resp.raise_for_status()
                return {"id": resp.json().get("message_id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Instagram send message failed: %s", e.response.text)
            return {"error": e.response.text[:500], "success": False}

    # ── Hashtag / Trend Search ───────────────────────────────────────────────

    def search_hashtag(self, access_token: str, hashtag: str, **kwargs) -> list[dict]:
        """
        Search for recent media by hashtag. Requires instagram_manage_insights.
        kwargs: ig_user_id
        """
        ig_user_id = kwargs.get("ig_user_id", "")
        if not ig_user_id:
            return []

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                # Step 1: Get hashtag ID
                tag_resp = client.get(f"{FB_API_BASE}/ig_hashtag_search", params={
                    "user_id": ig_user_id,
                    "q": hashtag.lstrip("#"),
                    "access_token": access_token,
                })
                tag_resp.raise_for_status()
                tags = tag_resp.json().get("data", [])
                if not tags:
                    return []

                tag_id = tags[0]["id"]

                # Step 2: Get recent media for this hashtag
                media_resp = client.get(f"{FB_API_BASE}/{tag_id}/recent_media", params={
                    "user_id": ig_user_id,
                    "fields": "id,caption,like_count,comments_count,timestamp,permalink",
                    "limit": kwargs.get("limit", 25),
                    "access_token": access_token,
                })
                media_resp.raise_for_status()
                return [
                    {
                        "id": m.get("id", ""),
                        "caption": m.get("caption", ""),
                        "likes": m.get("like_count", 0),
                        "comments": m.get("comments_count", 0),
                        "timestamp": m.get("timestamp", ""),
                        "url": m.get("permalink", ""),
                    }
                    for m in media_resp.json().get("data", [])
                ]
        except httpx.HTTPStatusError as e:
            logger.error("Instagram hashtag search failed: %s", e.response.text)
            return []

    # ── User Info ────────────────────────────────────────────────────────────

    def get_user_info(self, access_token: str) -> dict:
        return {}

    def validate_token(self, access_token: str) -> bool:
        """Validate via token debug endpoint."""
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(f"{FB_API_BASE}/debug_token", params={
                    "input_token": access_token,
                    "access_token": f"{self.app_id}|{self.app_secret}",
                })
                resp.raise_for_status()
                return resp.json().get("data", {}).get("is_valid", False)
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────────────
    # PROFILE AUDIT — Instagram Business
    # ──────────────────────────────────────────────────────────────────
    # IG Graph API exposes: username, name, biography, website,
    # profile_picture_url, ig_id, followers_count, media_count.
    # Of those, biography and website are user-editable via PATCH.
    _IG_AUDIT_FIELDS = {
        "biography": 35,        # The bio — most important
        "website": 25,
        "name": 15,             # Display name
        "profile_picture_url": 15,
        "username": 10,
    }
    _IG_THIN_THRESHOLDS = {
        "biography": 30,
        "website": 8,
        "name": 3,
    }

    def audit_profile(self, access_token: str, **kwargs) -> ProfileSnapshot:
        snap = ProfileSnapshot()
        ig_user_id = kwargs.get("ig_user_id") or kwargs.get("platform_user_id")
        if not ig_user_id:
            snap.error = "Instagram audit requires ig_user_id."
            return snap

        fields_param = ",".join(self._IG_AUDIT_FIELDS.keys())
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.get(
                    f"{FB_API_BASE}/{ig_user_id}",
                    params={"fields": fields_param, "access_token": access_token},
                )
                if resp.status_code in (401, 403):
                    raise PlatformAuthError(f"Instagram auth error: {resp.text[:200]}")
                resp.raise_for_status()
                data = resp.json()
        except PlatformAuthError:
            raise
        except Exception as exc:
            snap.error = f"Instagram audit failed: {exc}"
            return snap

        snap.raw_profile = FacebookProvider._truncate_raw(data)

        present, missing, thin = {}, [], []
        score = 0
        total_weight = sum(self._IG_AUDIT_FIELDS.values())

        for field_name, weight in self._IG_AUDIT_FIELDS.items():
            value = data.get(field_name) or ""
            value = str(value).strip()
            if value:
                present[field_name] = value
                threshold = self._IG_THIN_THRESHOLDS.get(field_name)
                if threshold and len(value) < threshold:
                    thin.append(field_name)
                    score += weight * 0.5
                else:
                    score += weight
            else:
                missing.append(field_name)

        snap.fields_present = present
        snap.fields_missing = missing
        snap.fields_thin = thin
        snap.completeness_score = int(round((score / total_weight) * 100)) if total_weight else 0
        return snap

    # IG Graph API supports updating biography + website via POST
    # (multipart not required for these scalar fields). profile_picture_url
    # cannot be updated via API — Meta restricts it to the mobile app.
    _IG_WRITABLE_FIELDS = {"biography", "website"}

    def update_profile(
        self, access_token: str, updates: dict, **kwargs,
    ) -> ProfileUpdateResult:
        if not updates:
            return ProfileUpdateResult(success=False, error="No updates provided.")
        field_name, new_value = next(iter(updates.items()))
        ig_user_id = kwargs.get("ig_user_id") or kwargs.get("platform_user_id")
        if not ig_user_id:
            return ProfileUpdateResult(
                success=False, field_name=field_name,
                error="Instagram update requires ig_user_id.",
            )
        if field_name not in self._IG_WRITABLE_FIELDS:
            return ProfileUpdateResult(
                success=False, field_name=field_name,
                error=f"Field '{field_name}' is not writable on Instagram via API "
                      "(profile picture must be changed in the mobile app).",
            )

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(
                    f"{FB_API_BASE}/{ig_user_id}",
                    data={field_name: new_value, "access_token": access_token},
                )
                if resp.status_code in (401, 403):
                    raise PlatformAuthError(f"Instagram auth error: {resp.text[:200]}")
                if not resp.is_success:
                    return ProfileUpdateResult(
                        success=False, field_name=field_name,
                        error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                        api_response=FacebookProvider._safe_json(resp),
                    )
                body = FacebookProvider._safe_json(resp)
                # Re-fetch to see what IG actually stored
                check = client.get(
                    f"{FB_API_BASE}/{ig_user_id}",
                    params={"fields": field_name, "access_token": access_token},
                )
                applied = str(check.json().get(field_name, new_value)) if check.is_success else str(new_value)
        except PlatformAuthError:
            raise
        except Exception as exc:
            return ProfileUpdateResult(
                success=False, field_name=field_name,
                error=f"Instagram update failed: {exc}",
            )

        return ProfileUpdateResult(
            success=True, field_name=field_name,
            applied_value=applied, api_response=body,
        )


# ── Auto-register both providers ─────────────────────────────────────────────
register_provider(FacebookProvider())
register_provider(InstagramProvider())
