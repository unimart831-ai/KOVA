"""
Instagram / Facebook Provider (via Facebook Graph API).

Instagram posting uses the Facebook Graph API — Instagram accounts must be
connected through a Facebook Page. This provider handles both Facebook Pages
and Instagram Professional accounts.

Scopes: pages_show_list, pages_manage_posts, instagram_basic, instagram_content_publish
Docs: https://developers.facebook.com/docs/instagram-api/
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

FB_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FB_API_BASE = "https://graph.facebook.com/v19.0"

# Scopes for Facebook Login + Page management
# pages_show_list + pages_manage_posts require "Content management" use case in Meta portal
# instagram_basic + instagram_content_publish require Instagram use case (add later)
FB_SCOPES = "email,public_profile,pages_show_list,pages_manage_posts,pages_read_engagement"

# Add these when Instagram use case is enabled in Meta portal:
# FB_SCOPES_WITH_INSTAGRAM = FB_SCOPES + ",instagram_basic,instagram_content_publish"


class FacebookProvider(BaseProvider):
    """Facebook Pages provider."""
    platform_name = "facebook"

    def __init__(self):
        self.app_id = getattr(settings, "FACEBOOK_APP_ID", "")
        self.app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "scope": FB_SCOPES,
            "state": state,
            "response_type": "code",
        }
        return f"{FB_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        # Exchange code for short-lived token
        with httpx.Client() as client:
            resp = client.get(
                FB_TOKEN_URL,
                params={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            tokens = resp.json()

            short_token = tokens["access_token"]

            # Exchange for long-lived token (60 days)
            long_resp = client.get(
                FB_TOKEN_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "fb_exchange_token": short_token,
                },
            )
            long_resp.raise_for_status()
            long_tokens = long_resp.json()
            access_token = long_tokens.get("access_token", short_token)

            # Get user profile
            me_resp = client.get(
                f"{FB_API_BASE}/me",
                params={
                    "fields": "id,name,picture",
                    "access_token": access_token,
                },
            )
            me_resp.raise_for_status()
            user = me_resp.json()

            # Get pages the user manages (requires pages_show_list scope)
            pages = []
            try:
                pages_resp = client.get(
                    f"{FB_API_BASE}/me/accounts",
                    params={"access_token": access_token},
                )
                pages_resp.raise_for_status()
                pages = pages_resp.json().get("data", [])
            except Exception:
                logger.info("Could not fetch pages — pages_show_list scope may not be granted")

        expires_at = None
        if "expires_in" in long_tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=long_tokens["expires_in"])

        return OAuthResult(
            platform_user_id=user.get("id", ""),
            username=user.get("name", "").lower().replace(" ", ""),
            display_name=user.get("name", ""),
            avatar_url=user.get("picture", {}).get("data", {}).get("url", ""),
            access_token=access_token,
            refresh_token="",  # Facebook uses long-lived tokens instead
            token_expires_at=expires_at,
            token_scope=FB_SCOPES,
            metadata={"pages": [{"id": p["id"], "name": p["name"], "access_token": p["access_token"]} for p in pages]},
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        # Facebook long-lived tokens can be refreshed by exchanging again
        # However, they typically last 60 days. For now, re-auth is required.
        raise NotImplementedError(
            "Facebook long-lived tokens last ~60 days. Re-authentication required after expiry."
        )

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        page_id = kwargs.get("page_id", "")
        page_token = kwargs.get("page_access_token", access_token)

        if not page_id:
            return PublishResult(success=False, error="page_id is required for Facebook posting")

        payload = {"message": content, "access_token": page_token}

        try:
            with httpx.Client() as client:
                if media_urls:
                    # Photo post
                    payload["url"] = media_urls[0]
                    resp = client.post(f"{FB_API_BASE}/{page_id}/photos", data=payload)
                else:
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
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{FB_API_BASE}/{platform_post_id}",
                    params={
                        "fields": "likes.summary(true),comments.summary(true),shares",
                        "access_token": access_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return PostMetrics(
                    likes=data.get("likes", {}).get("summary", {}).get("total_count", 0),
                    comments=data.get("comments", {}).get("summary", {}).get("total_count", 0),
                    shares=data.get("shares", {}).get("count", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Facebook metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    def get_user_info(self, access_token: str) -> dict:
        with httpx.Client() as client:
            resp = client.get(
                f"{FB_API_BASE}/me",
                params={"fields": "id,name,picture", "access_token": access_token},
            )
            resp.raise_for_status()
            return resp.json()


class InstagramProvider(BaseProvider):
    """Instagram Professional Account provider (via Facebook Graph API)."""
    platform_name = "instagram"

    def __init__(self):
        self.app_id = getattr(settings, "FACEBOOK_APP_ID", "")
        self.app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        # Uses same Facebook flow — Instagram accounts linked to FB Pages
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "scope": FB_SCOPES,
            "state": state,
            "response_type": "code",
        }
        return f"{FB_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        with httpx.Client() as client:
            # Exchange code for token (same as Facebook)
            resp = client.get(
                FB_TOKEN_URL,
                params={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            tokens = resp.json()
            access_token = tokens["access_token"]

            # Exchange for long-lived token
            long_resp = client.get(
                FB_TOKEN_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "fb_exchange_token": access_token,
                },
            )
            long_resp.raise_for_status()
            long_tokens = long_resp.json()
            access_token = long_tokens.get("access_token", access_token)

            # Find Instagram Business Account linked to user's pages
            pages_resp = client.get(
                f"{FB_API_BASE}/me/accounts",
                params={"access_token": access_token},
            )
            pages_resp.raise_for_status()
            pages = pages_resp.json().get("data", [])

            ig_account = None
            page_token = ""
            for page in pages:
                ig_resp = client.get(
                    f"{FB_API_BASE}/{page['id']}",
                    params={
                        "fields": "instagram_business_account",
                        "access_token": page["access_token"],
                    },
                )
                ig_resp.raise_for_status()
                ig_data = ig_resp.json().get("instagram_business_account")
                if ig_data:
                    ig_account = ig_data
                    page_token = page["access_token"]
                    break

            if not ig_account:
                raise ValueError("No Instagram Business Account found linked to your Facebook pages")

            ig_id = ig_account["id"]

            # Fetch IG profile
            ig_profile_resp = client.get(
                f"{FB_API_BASE}/{ig_id}",
                params={
                    "fields": "id,username,name,profile_picture_url",
                    "access_token": page_token,
                },
            )
            ig_profile_resp.raise_for_status()
            ig_profile = ig_profile_resp.json()

        expires_at = None
        if "expires_in" in long_tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=long_tokens["expires_in"])

        return OAuthResult(
            platform_user_id=ig_id,
            username=ig_profile.get("username", ""),
            display_name=ig_profile.get("name", ""),
            avatar_url=ig_profile.get("profile_picture_url", ""),
            access_token=page_token,  # Use page token for IG API calls
            refresh_token="",
            token_expires_at=expires_at,
            token_scope=FB_SCOPES,
            metadata={"ig_business_id": ig_id, "user_access_token": access_token},
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        raise NotImplementedError(
            "Instagram tokens (via Facebook) last ~60 days. Re-authentication required."
        )

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        ig_user_id = kwargs.get("ig_user_id", "")
        if not ig_user_id:
            return PublishResult(success=False, error="ig_user_id is required")

        try:
            with httpx.Client() as client:
                if media_urls:
                    # Step 1: Create media container
                    container_resp = client.post(
                        f"{FB_API_BASE}/{ig_user_id}/media",
                        data={
                            "image_url": media_urls[0],
                            "caption": content,
                            "access_token": access_token,
                        },
                    )
                    container_resp.raise_for_status()
                    container_id = container_resp.json()["id"]

                    # Step 2: Publish the container
                    pub_resp = client.post(
                        f"{FB_API_BASE}/{ig_user_id}/media_publish",
                        data={
                            "creation_id": container_id,
                            "access_token": access_token,
                        },
                    )
                    pub_resp.raise_for_status()
                    post_id = pub_resp.json().get("id", "")
                else:
                    return PublishResult(
                        success=False,
                        error="Instagram requires at least one image for publishing.",
                    )

                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    url=f"https://www.instagram.com/p/{post_id}/",
                )
        except httpx.HTTPStatusError as e:
            logger.error("Instagram publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{FB_API_BASE}/{platform_post_id}/insights",
                    params={
                        "metric": "impressions,reach,likes,comments,shares,saved",
                        "access_token": access_token,
                    },
                )
                resp.raise_for_status()
                metrics_data = {m["name"]: m["values"][0]["value"] for m in resp.json().get("data", [])}
                return PostMetrics(
                    likes=metrics_data.get("likes", 0),
                    comments=metrics_data.get("comments", 0),
                    shares=metrics_data.get("shares", 0),
                    impressions=metrics_data.get("impressions", 0),
                    reach=metrics_data.get("reach", 0),
                    saves=metrics_data.get("saved", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Instagram metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    def get_user_info(self, access_token: str) -> dict:
        # This needs the IG user ID — stored in metadata
        return {}


# Auto-register both providers
register_provider(FacebookProvider())
register_provider(InstagramProvider())
