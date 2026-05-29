"""
Pinterest OAuth 2.0 Provider.

Uses Pinterest API v5 for pin creation and analytics.

Capability matrix:
─────────────────────────────────────────────────────────────────────
CAPABILITY                           │ API ENDPOINT
─────────────────────────────────────────────────────────────────────
Create pin                           │ POST /v5/pins
Get pin                              │ GET /v5/pins/{pin_id}
Get pin analytics                    │ GET /v5/pins/{pin_id}/analytics
List boards                          │ GET /v5/boards
Create board                         │ POST /v5/boards
Get user info                        │ GET /v5/user_account
─────────────────────────────────────────────────────────────────────
Docs: https://developers.pinterest.com/docs/api/v5/
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

PINTEREST_AUTH_URL = "https://www.pinterest.com/oauth/"
PINTEREST_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
PINTEREST_API_BASE = "https://api.pinterest.com/v5"

PINTEREST_SCOPES = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"


class PinterestProvider(BaseProvider):
    platform_name = "pinterest"

    def __init__(self):
        self.client_id = getattr(settings, "PINTEREST_APP_ID", "")
        self.client_secret = getattr(settings, "PINTEREST_APP_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": PINTEREST_SCOPES,
            "state": state,
        }
        return f"{PINTEREST_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        with httpx.Client() as client:
            resp = client.post(
                PINTEREST_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

            # Fetch user profile
            user_resp = client.get(
                f"{PINTEREST_API_BASE}/user_account",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            user_resp.raise_for_status()
            user = user_resp.json()

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

        return OAuthResult(
            platform_user_id=user.get("id", ""),
            username=user.get("username", ""),
            display_name=user.get("business_name", user.get("username", "")),
            avatar_url=user.get("profile_image", ""),
            access_token=tokens.get("access_token", ""),
            refresh_token=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
            token_scope=PINTEREST_SCOPES,
            metadata={
                "account_type": user.get("account_type", ""),
                "follower_count": user.get("follower_count", 0),
                "pin_count": user.get("pin_count", 0),
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        with httpx.Client() as client:
            resp = client.post(
                PINTEREST_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

        result = {"access_token": tokens["access_token"]}
        if "refresh_token" in tokens:
            result["refresh_token"] = tokens["refresh_token"]
        if "expires_in" in tokens:
            result["expires_in"] = tokens["expires_in"]
            result["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        return result

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Create a pin on Pinterest.
        kwargs can include: board_id, title, link, alt_text.
        media_urls[0] should be the image URL.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        board_id = kwargs.get("board_id", "")

        if not board_id:
            # Try to get the first board
            try:
                with httpx.Client() as client:
                    boards_resp = client.get(
                        f"{PINTEREST_API_BASE}/boards",
                        headers=headers,
                    )
                    boards_resp.raise_for_status()
                    boards = boards_resp.json().get("items", [])
                    if boards:
                        board_id = boards[0]["id"]
                    else:
                        return PublishResult(success=False, error="No boards found. Create a board first.")
            except httpx.HTTPStatusError as e:
                return PublishResult(success=False, error=f"Failed to fetch boards: {e}")

        pin_data = {
            "board_id": board_id,
            "title": kwargs.get("title", content[:100]),
            "description": content,
            "alt_text": kwargs.get("alt_text", content[:500]),
        }

        if kwargs.get("link"):
            pin_data["link"] = kwargs["link"]

        if media_urls:
            pin_data["media_source"] = {
                "source_type": "image_url",
                "url": media_urls[0],
            }
        else:
            return PublishResult(success=False, error="Pinterest requires an image. No media URL provided.")

        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{PINTEREST_API_BASE}/pins",
                    json=pin_data,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                pin_id = data.get("id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=pin_id,
                    url=f"https://www.pinterest.com/pin/{pin_id}/",
                )
        except httpx.HTTPStatusError as e:
            logger.error("Pinterest publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{PINTEREST_API_BASE}/pins/{platform_post_id}/analytics",
                    params={
                        "start_date": (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"),
                        "end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "metric_types": "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK",
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json().get("all", {}).get("lifetime_metrics", {})
                return PostMetrics(
                    impressions=data.get("IMPRESSION", 0),
                    saves=data.get("SAVE", 0),
                    clicks=data.get("PIN_CLICK", 0) + data.get("OUTBOUND_CLICK", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Pinterest metrics failed: %s", e.response.text)
            return PostMetrics()


# Auto-register
register_provider(PinterestProvider())
