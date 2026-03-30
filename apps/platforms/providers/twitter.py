"""
X/Twitter OAuth 2.0 Provider (with PKCE).

Twitter API v2 uses OAuth 2.0 with PKCE for user-context authentication.
Scopes: tweet.read, tweet.write, users.read, offline.access, like.write, like.read

Full capability matrix:
─────────────────────────────────────────────────────────────────────
CAPABILITY                           │ API ENDPOINT
─────────────────────────────────────────────────────────────────────
Publish tweet                        │ POST /2/tweets
Publish thread                       │ POST /2/tweets (chained reply_to)
Reply to tweet                       │ POST /2/tweets (in_reply_to_tweet_id)
Retweet                              │ POST /2/users/:id/retweets
Undo retweet                         │ DELETE /2/users/:id/retweets/:tweet_id
Like tweet                           │ POST /2/users/:id/likes
Unlike tweet                         │ DELETE /2/users/:id/likes/:tweet_id
Delete tweet                         │ DELETE /2/tweets/:id
Get tweet metrics                    │ GET /2/tweets/:id (public_metrics)
Get mentions                         │ GET /2/users/:id/mentions
Get user info                        │ GET /2/users/me
Schedule (via Kova)                  │ Internal scheduler
─────────────────────────────────────────────────────────────────────
Docs: https://developer.twitter.com/en/docs/authentication/oauth-2-0
"""

import hashlib
import logging
import secrets
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

TWITTER_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TWITTER_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
TWITTER_API_BASE = "https://api.twitter.com/2"

TWITTER_SCOPES = "tweet.read tweet.write users.read offline.access like.write like.read"


class TwitterProvider(BaseProvider):
    platform_name = "twitter"

    def __init__(self):
        self.client_id = getattr(settings, "TWITTER_CLIENT_ID", "")
        self.client_secret = getattr(settings, "TWITTER_CLIENT_SECRET", "")

    def _generate_pkce(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge."""
        code_verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = secrets.token_urlsafe(64)[:43]  # placeholder
        # Proper S256 challenge
        import base64
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return code_verifier, code_challenge

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        code_verifier, code_challenge = self._generate_pkce()
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": TWITTER_SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        # Store code_verifier in state metadata (retrieved in callback)
        # We append it to state: "state|code_verifier"
        combined_state = f"{state}|{code_verifier}"
        params["state"] = combined_state
        return f"{TWITTER_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, code: str, redirect_uri: str,
                        code_verifier: str = "") -> OAuthResult:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }
        with httpx.Client() as client:
            resp = client.post(
                TWITTER_TOKEN_URL,
                data=data,
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

            # Fetch user profile
            user_resp = client.get(
                f"{TWITTER_API_BASE}/users/me",
                params={"user.fields": "id,name,username,profile_image_url"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            user_resp.raise_for_status()
            user_data = user_resp.json().get("data", {})

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

        return OAuthResult(
            platform_user_id=user_data.get("id", ""),
            username=user_data.get("username", ""),
            display_name=user_data.get("name", ""),
            avatar_url=user_data.get("profile_image_url", ""),
            access_token=tokens.get("access_token", ""),
            refresh_token=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
            token_scope=tokens.get("scope", ""),
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        with httpx.Client() as client:
            resp = client.post(
                TWITTER_TOKEN_URL,
                data=data,
                auth=(self.client_id, self.client_secret),
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
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {"text": content}

        # Media upload would go through v1.1 media/upload endpoint
        # then attach media_ids — simplified for now
        if media_urls:
            payload["text"] = content  # Media upload TBD

        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{TWITTER_API_BASE}/tweets",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                tweet_id = data.get("id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=tweet_id,
                    url=f"https://twitter.com/i/web/status/{tweet_id}",
                )
        except httpx.HTTPStatusError as e:
            logger.error("Twitter publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"tweet.fields": "public_metrics"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{TWITTER_API_BASE}/tweets/{platform_post_id}",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                metrics = resp.json().get("data", {}).get("public_metrics", {})
                return PostMetrics(
                    likes=metrics.get("like_count", 0),
                    comments=metrics.get("reply_count", 0),
                    shares=metrics.get("retweet_count", 0) + metrics.get("quote_count", 0),
                    impressions=metrics.get("impression_count", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Twitter metrics fetch failed: %s", e.response.text)
            return PostMetrics()

    def get_mentions(self, access_token: str, since_id: Optional[str] = None) -> list[dict]:
        headers = {"Authorization": f"Bearer {access_token}"}
        # First get the authenticated user's ID
        try:
            with httpx.Client() as client:
                me_resp = client.get(
                    f"{TWITTER_API_BASE}/users/me",
                    headers=headers,
                )
                me_resp.raise_for_status()
                user_id = me_resp.json()["data"]["id"]

                params = {"tweet.fields": "author_id,created_at,text"}
                if since_id:
                    params["since_id"] = since_id

                resp = client.get(
                    f"{TWITTER_API_BASE}/users/{user_id}/mentions",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                mentions = []
                for tweet in resp.json().get("data", []):
                    mentions.append({
                        "id": tweet["id"],
                        "author": tweet.get("author_id", ""),
                        "text": tweet.get("text", ""),
                        "created_at": tweet.get("created_at", ""),
                        "type": "mention",
                    })
                return mentions
        except httpx.HTTPStatusError as e:
            logger.error("Twitter mentions fetch failed: %s", e.response.text)
            return []

    def get_user_info(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client() as client:
            resp = client.get(
                f"{TWITTER_API_BASE}/users/me",
                params={"user.fields": "id,name,username,profile_image_url"},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})

    def revoke_token(self, access_token: str) -> bool:
        try:
            with httpx.Client() as client:
                resp = client.post(
                    "https://api.twitter.com/2/oauth2/revoke",
                    data={"token": access_token, "client_id": self.client_id},
                    auth=(self.client_id, self.client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    # ─── Thread / Reply ──────────────────────────────────────────────────────

    def publish_thread(self, access_token: str, tweets: list[str],
                       **kwargs) -> list[PublishResult]:
        """Publish a thread — list of tweets chained via in_reply_to_tweet_id."""
        headers = {"Authorization": f"Bearer {access_token}"}
        results = []
        reply_to = None

        for text in tweets:
            payload = {"text": text}
            if reply_to:
                payload["reply"] = {"in_reply_to_tweet_id": reply_to}
            try:
                with httpx.Client() as client:
                    resp = client.post(
                        f"{TWITTER_API_BASE}/tweets",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json().get("data", {})
                    tweet_id = data.get("id", "")
                    reply_to = tweet_id
                    results.append(PublishResult(
                        success=True,
                        platform_post_id=tweet_id,
                        url=f"https://twitter.com/i/web/status/{tweet_id}",
                    ))
            except httpx.HTTPStatusError as e:
                logger.error("Twitter thread publish failed: %s", e.response.text)
                results.append(PublishResult(success=False, error=str(e)))
                break  # Stop thread on failure
        return results

    def reply_to_comment(self, access_token: str, comment_id: str,
                         message: str, **kwargs) -> dict:
        """Reply to a tweet (comment_id is the tweet ID being replied to)."""
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "text": message,
            "reply": {"in_reply_to_tweet_id": comment_id},
        }
        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{TWITTER_API_BASE}/tweets",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                return {"id": data.get("id", ""), "success": True}
        except httpx.HTTPStatusError as e:
            logger.error("Twitter reply failed: %s", e.response.text)
            return {"error": str(e), "success": False}

    # ─── Like / Retweet ──────────────────────────────────────────────────────

    def react_to_post(self, access_token: str, post_id: str,
                      reaction: str = "LIKE", **kwargs) -> dict:
        """Like or retweet a tweet."""
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with httpx.Client() as client:
                # Get current user ID
                me_resp = client.get(
                    f"{TWITTER_API_BASE}/users/me",
                    headers=headers,
                )
                me_resp.raise_for_status()
                user_id = me_resp.json()["data"]["id"]

                if reaction.upper() == "RETWEET":
                    resp = client.post(
                        f"{TWITTER_API_BASE}/users/{user_id}/retweets",
                        json={"tweet_id": post_id},
                        headers=headers,
                    )
                else:  # Default: LIKE
                    resp = client.post(
                        f"{TWITTER_API_BASE}/users/{user_id}/likes",
                        json={"tweet_id": post_id},
                        headers=headers,
                    )
                resp.raise_for_status()
                return {"success": True, "action": reaction.lower()}
        except httpx.HTTPStatusError as e:
            logger.error("Twitter %s failed: %s", reaction, e.response.text)
            return {"error": str(e), "success": False}

    # ─── Delete ──────────────────────────────────────────────────────────────

    def delete_post(self, access_token: str, platform_post_id: str,
                    **kwargs) -> bool:
        """Delete a tweet by ID."""
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with httpx.Client() as client:
                resp = client.delete(
                    f"{TWITTER_API_BASE}/tweets/{platform_post_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json().get("data", {}).get("deleted", False)
        except httpx.HTTPStatusError as e:
            logger.error("Twitter delete failed: %s", e.response.text)
            return False


# Auto-register
register_provider(TwitterProvider())
