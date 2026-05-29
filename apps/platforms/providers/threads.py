"""
Threads Provider (via Instagram/Meta Graph API).

Threads uses the Meta Graph API (same credentials as Instagram).
Publishing requires a two-step process: create media container → publish.

Capability matrix:
─────────────────────────────────────────────────────────────────────
CAPABILITY                           │ API ENDPOINT
─────────────────────────────────────────────────────────────────────
Create text post                     │ POST /{user_id}/threads
Create image post                    │ POST /{user_id}/threads + media_url
Create carousel                      │ POST /{user_id}/threads (carousel)
Publish container                    │ POST /{user_id}/threads_publish
Get post metrics                     │ GET /{thread_id}/insights
Get user profile                     │ GET /{user_id}/threads_profile
Get replies                          │ GET /{thread_id}/replies
Reply to thread                      │ POST /{user_id}/threads (reply_to)
─────────────────────────────────────────────────────────────────────
Docs: https://developers.facebook.com/docs/threads
"""

import logging
import time
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

THREADS_AUTH_URL = "https://threads.net/oauth/authorize"
GRAPH_API_BASE = "https://graph.threads.net/v1.0"
THREADS_TOKEN_URL = f"{GRAPH_API_BASE}/oauth/access_token"

THREADS_SCOPES = "threads_basic,threads_content_publish,threads_manage_insights,threads_manage_replies,threads_read_replies"


class ThreadsProvider(BaseProvider):
    platform_name = "threads"

    def __init__(self):
        self.app_id = getattr(settings, "THREADS_APP_ID", "") or getattr(settings, "FACEBOOK_APP_ID", "")
        self.app_secret = getattr(settings, "THREADS_APP_SECRET", "") or getattr(settings, "FACEBOOK_APP_SECRET", "")

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "scope": THREADS_SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{THREADS_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        with httpx.Client() as client:
            # Exchange code for short-lived token
            resp = client.post(
                THREADS_TOKEN_URL,
                data={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            short_token = resp.json()

            # Exchange for long-lived token (60 days)
            ll_resp = client.get(
                f"{GRAPH_API_BASE}/access_token",
                params={
                    "grant_type": "th_exchange_token",
                    "client_secret": self.app_secret,
                    "access_token": short_token["access_token"],
                },
            )
            ll_resp.raise_for_status()
            long_token = ll_resp.json()

            access_token = long_token.get("access_token", short_token["access_token"])
            expires_in = long_token.get("expires_in", short_token.get("expires_in", 5184000))

            # Fetch user profile
            user_id = short_token.get("user_id", "me")
            profile_resp = client.get(
                f"{GRAPH_API_BASE}/{user_id}",
                params={
                    "fields": "id,username,name,threads_profile_picture_url,threads_biography",
                    "access_token": access_token,
                },
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return OAuthResult(
            platform_user_id=profile.get("id", str(user_id)),
            username=profile.get("username", ""),
            display_name=profile.get("name", profile.get("username", "")),
            avatar_url=profile.get("threads_profile_picture_url", ""),
            access_token=access_token,
            refresh_token="",  # Threads uses long-lived tokens, refreshed via exchange
            token_expires_at=expires_at,
            token_scope=THREADS_SCOPES,
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh a long-lived Threads token (before it expires in 60 days)."""
        # Threads refreshes by exchanging the current long-lived token
        # The refresh_token field actually stores the access_token for refresh
        with httpx.Client() as client:
            resp = client.get(
                f"{GRAPH_API_BASE}/refresh_access_token",
                params={
                    "grant_type": "th_refresh_token",
                    "access_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        result = {"access_token": data["access_token"]}
        if "expires_in" in data:
            result["expires_in"] = data["expires_in"]
            result["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        return result

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Two-step publish: create container → publish container.
        Supports text, image, and carousel posts.
        """
        headers = {}
        user_id = kwargs.get("user_id", "me")

        try:
            with httpx.Client(timeout=60) as client:
                # Step 1: Create media container
                container_data = {
                    "text": content,
                    "access_token": access_token,
                }

                if media_urls and len(media_urls) == 1:
                    # Single image post
                    container_data["media_type"] = "IMAGE"
                    container_data["image_url"] = media_urls[0]
                elif media_urls and len(media_urls) > 1:
                    # Carousel — create individual containers first
                    child_ids = []
                    for url in media_urls[:10]:  # Max 10 items
                        child_resp = client.post(
                            f"{GRAPH_API_BASE}/{user_id}/threads",
                            data={
                                "media_type": "IMAGE",
                                "image_url": url,
                                "is_carousel_item": "true",
                                "access_token": access_token,
                            },
                        )
                        child_resp.raise_for_status()
                        child_ids.append(child_resp.json()["id"])

                    container_data["media_type"] = "CAROUSEL"
                    container_data["children"] = ",".join(child_ids)
                else:
                    # Text-only post
                    container_data["media_type"] = "TEXT"

                # Handle reply_to
                if kwargs.get("reply_to_id"):
                    container_data["reply_to_id"] = kwargs["reply_to_id"]

                resp = client.post(
                    f"{GRAPH_API_BASE}/{user_id}/threads",
                    data=container_data,
                )
                resp.raise_for_status()
                container_id = resp.json()["id"]

                # Step 2: Wait for container to be ready (poll)
                for _ in range(10):
                    status_resp = client.get(
                        f"{GRAPH_API_BASE}/{container_id}",
                        params={
                            "fields": "status",
                            "access_token": access_token,
                        },
                    )
                    status_resp.raise_for_status()
                    status = status_resp.json().get("status", "")
                    if status == "FINISHED":
                        break
                    if status == "ERROR":
                        return PublishResult(success=False, error="Media container creation failed")
                    time.sleep(2)

                # Step 3: Publish
                pub_resp = client.post(
                    f"{GRAPH_API_BASE}/{user_id}/threads_publish",
                    data={
                        "creation_id": container_id,
                        "access_token": access_token,
                    },
                )
                pub_resp.raise_for_status()
                thread_id = pub_resp.json().get("id", "")

                return PublishResult(
                    success=True,
                    platform_post_id=thread_id,
                    url=f"https://www.threads.net/post/{thread_id}",
                )

        except httpx.HTTPStatusError as e:
            logger.error("Threads publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{GRAPH_API_BASE}/{platform_post_id}/insights",
                    params={
                        "metric": "views,likes,replies,reposts,quotes",
                        "access_token": access_token,
                    },
                )
                resp.raise_for_status()
                metrics_data = resp.json().get("data", [])
                metrics = {}
                for m in metrics_data:
                    metrics[m["name"]] = m.get("values", [{}])[0].get("value", 0)

                return PostMetrics(
                    likes=metrics.get("likes", 0),
                    comments=metrics.get("replies", 0),
                    shares=metrics.get("reposts", 0) + metrics.get("quotes", 0),
                    impressions=metrics.get("views", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Threads metrics failed: %s", e.response.text)
            return PostMetrics()

    def get_comments(self, access_token: str, post_id: str, **kwargs) -> list[dict]:
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{GRAPH_API_BASE}/{post_id}/replies",
                    params={
                        "fields": "id,text,username,timestamp",
                        "access_token": access_token,
                    },
                )
                resp.raise_for_status()
                comments = []
                for reply in resp.json().get("data", []):
                    comments.append({
                        "id": reply["id"],
                        "author_id": reply.get("username", ""),
                        "author_name": reply.get("username", ""),
                        "text": reply.get("text", ""),
                        "created_at": reply.get("timestamp", ""),
                    })
                return comments
        except httpx.HTTPStatusError as e:
            logger.error("Threads comments failed: %s", e.response.text)
            return []


# Auto-register
register_provider(ThreadsProvider())
