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
    BaseProvider, OAuthResult, PlatformAuthError, PostMetrics, PublishResult,
)
from apps.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

# ── Graph API versioning ─────────────────────────────────────────────────────
FB_API_VERSION = "v25.0"
FB_AUTH_URL = f"https://www.facebook.com/{FB_API_VERSION}/dialog/oauth"
FB_TOKEN_URL = f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token"
FB_API_BASE = f"https://graph.facebook.com/{FB_API_VERSION}"

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
                "pages": [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "access_token": p["access_token"],
                        "picture_url": p.get("picture", {}).get("data", {}).get("url", ""),
                    }
                    for p in pages
                ],
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

        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 5184000),  # default 60 days
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
                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    url=f"https://www.facebook.com/{post_id}",
                )
        except httpx.HTTPStatusError as e:
            logger.error("Facebook publish failed: %s", e.response.text)
            return PublishResult(success=False, error=e.response.text[:500])

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
            logger.error("Facebook video publish failed: %s", e.response.text)
            return PublishResult(success=False, error=e.response.text[:500])

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
                # Step 1: Basic engagement (likes, comments, shares) — always works
                resp = client.get(f"{FB_API_BASE}/{platform_post_id}", params={
                    "fields": "likes.summary(true),comments.summary(true),shares",
                    "access_token": access_token,
                })
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
        page_token = kwargs.get("page_access_token", access_token)
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(f"{FB_API_BASE}/me/messages", json={
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
        raise NotImplementedError(
            "Instagram tokens (via Facebook) last ~60 days. Re-authentication required."
        )

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

        if not ig_user_id:
            return PublishResult(success=False, error="ig_user_id is required")

        try:
            with httpx.Client(timeout=120.0) as client:
                if media_type == "CAROUSEL" and media_urls and len(media_urls) > 1:
                    return self._publish_carousel(client, access_token, ig_user_id, content, media_urls)
                elif media_type == "REELS":
                    video_url = kwargs.get("video_url", media_urls[0] if media_urls else "")
                    return self._publish_reels(client, access_token, ig_user_id, content, video_url)
                elif media_type == "STORIES":
                    return self._publish_story(client, access_token, ig_user_id, media_urls)
                elif media_urls:
                    return self._publish_single_image(client, access_token, ig_user_id, content, media_urls[0])
                else:
                    return PublishResult(
                        success=False,
                        error="Instagram requires media (image or video) for publishing.",
                    )
        except httpx.HTTPStatusError as e:
            logger.error("Instagram publish failed: %s", e.response.text)
            return PublishResult(success=False, error=e.response.text[:500])

    def _publish_single_image(self, client: httpx.Client, token: str,
                              ig_id: str, caption: str, image_url: str) -> PublishResult:
        """Single image post."""
        container = client.post(f"{FB_API_BASE}/{ig_id}/media", data={
            "image_url": image_url,
            "caption": caption,
            "access_token": token,
        })
        container.raise_for_status()
        container_id = container.json()["id"]

        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        return PublishResult(success=True, platform_post_id=post_id,
                             url=f"https://www.instagram.com/p/{post_id}/")

    def _publish_carousel(self, client: httpx.Client, token: str,
                          ig_id: str, caption: str, image_urls: list[str]) -> PublishResult:
        """Carousel post (2-10 images)."""
        child_ids = []
        for url in image_urls[:10]:
            child = client.post(f"{FB_API_BASE}/{ig_id}/media", data={
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": token,
            })
            child.raise_for_status()
            child_ids.append(child.json()["id"])

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

        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": carousel_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        return PublishResult(success=True, platform_post_id=post_id,
                             url=f"https://www.instagram.com/p/{post_id}/")

    def _publish_reels(self, client: httpx.Client, token: str,
                       ig_id: str, caption: str, video_url: str) -> PublishResult:
        """Publish a Reel."""
        if not video_url:
            return PublishResult(success=False, error="video_url is required for Reels")

        container = client.post(f"{FB_API_BASE}/{ig_id}/media", data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        })
        container.raise_for_status()
        container_id = container.json()["id"]

        # Poll until video is processed
        for _ in range(30):
            status = client.get(f"{FB_API_BASE}/{container_id}", params={
                "fields": "status_code",
                "access_token": token,
            })
            status.raise_for_status()
            if status.json().get("status_code") == "FINISHED":
                break
            time.sleep(2)

        pub = client.post(f"{FB_API_BASE}/{ig_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": token,
        })
        pub.raise_for_status()
        post_id = pub.json().get("id", "")
        return PublishResult(success=True, platform_post_id=post_id,
                             url=f"https://www.instagram.com/reel/{post_id}/")

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
            for _ in range(30):
                status = client.get(f"{FB_API_BASE}/{container_id}", params={
                    "fields": "status_code", "access_token": token,
                })
                status.raise_for_status()
                if status.json().get("status_code") == "FINISHED":
                    break
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


# ── Auto-register both providers ─────────────────────────────────────────────
register_provider(FacebookProvider())
register_provider(InstagramProvider())
