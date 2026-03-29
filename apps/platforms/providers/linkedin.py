"""
LinkedIn OAuth 2.0 Provider.

Uses OAuth 2.0 3-legged flow for member authentication.
Scopes: openid, profile, w_member_social (for posting)
Docs: https://learn.microsoft.com/en-us/linkedin/shared/authentication/
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

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_REST_BASE = "https://api.linkedin.com/rest"

LINKEDIN_SCOPES = "openid profile w_member_social"


class LinkedInProvider(BaseProvider):
    platform_name = "linkedin"

    def __init__(self):
        self.client_id = getattr(settings, "LINKEDIN_CLIENT_ID", "")
        self.client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": LINKEDIN_SCOPES,
            "state": state,
        }
        return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        with httpx.Client() as client:
            resp = client.post(
                LINKEDIN_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

            # Fetch user profile via /userinfo (OpenID Connect)
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            profile_resp = client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers=headers,
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

        # LinkedIn user ID from sub claim
        user_id = profile.get("sub", "")
        name = profile.get("name", "")
        picture = profile.get("picture", "")

        return OAuthResult(
            platform_user_id=user_id,
            username=name.lower().replace(" ", ""),
            display_name=name,
            avatar_url=picture,
            access_token=tokens.get("access_token", ""),
            refresh_token=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
            token_scope=tokens.get("scope", ""),
            metadata={"linkedin_sub": user_id},
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        with httpx.Client() as client:
            resp = client.post(
                LINKEDIN_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
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
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

        # Get the member URN first
        author_urn = kwargs.get("author_urn", "")
        if not author_urn:
            try:
                with httpx.Client() as client:
                    me_resp = client.get(
                        "https://api.linkedin.com/v2/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    me_resp.raise_for_status()
                    sub = me_resp.json().get("sub", "")
                    author_urn = f"urn:li:person:{sub}"
            except httpx.HTTPStatusError as e:
                return PublishResult(success=False, error=f"Failed to get user: {e}")

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{LINKEDIN_API_BASE}/ugcPosts",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                post_id = resp.json().get("id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=post_id,
                    url=f"https://www.linkedin.com/feed/update/{post_id}/",
                )
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        # LinkedIn social actions endpoint
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{LINKEDIN_API_BASE}/socialActions/{platform_post_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return PostMetrics(
                    likes=data.get("likesSummary", {}).get("totalLikes", 0),
                    comments=data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                    shares=data.get("shareStatistics", {}).get("shareCount", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    def get_user_info(self, access_token: str) -> dict:
        with httpx.Client() as client:
            resp = client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()


# Auto-register
register_provider(LinkedInProvider())
