"""
Bluesky Provider (AT Protocol).

Bluesky uses the AT Protocol — fully open, no app review needed.
Authentication via app password (not OAuth) — simpler flow.

Capability matrix:
─────────────────────────────────────────────────────────────────────
CAPABILITY                           │ API ENDPOINT
─────────────────────────────────────────────────────────────────────
Create post (text + images)          │ POST /xrpc/com.atproto.repo.createRecord
Upload image blob                    │ POST /xrpc/com.atproto.repo.uploadBlob
Get post                             │ GET /xrpc/app.bsky.feed.getPostThread
Get profile                          │ GET /xrpc/app.bsky.actor.getProfile
Get author feed                      │ GET /xrpc/app.bsky.feed.getAuthorFeed
Get notifications                    │ GET /xrpc/app.bsky.notification.listNotifications
─────────────────────────────────────────────────────────────────────
Docs: https://docs.bsky.app/
AT Protocol: https://atproto.com/
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from django.conf import settings

from apps.platforms.providers.base import (
    BaseProvider, OAuthResult, PostMetrics, PublishResult,
)
from apps.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

BSKY_API_BASE = "https://bsky.social/xrpc"


class BlueskyProvider(BaseProvider):
    """
    Bluesky uses app passwords instead of OAuth.
    The "connect" flow asks for handle + app password,
    then creates a session to get access/refresh tokens.
    """
    platform_name = "bluesky"

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        """
        Bluesky doesn't use OAuth — return a special URL that signals
        the view to show a handle + app password form instead.
        """
        return f"__bluesky_app_password__|{state}"

    def handle_callback(self, code: str, redirect_uri: str, **kwargs) -> OAuthResult:
        """Not used — Bluesky uses handle_app_password instead."""
        raise NotImplementedError("Use handle_app_password() for Bluesky")

    def handle_app_password(self, handle: str, app_password: str) -> OAuthResult:
        """
        Authenticate with Bluesky using handle + app password.
        Creates a session and returns tokens.
        """
        with httpx.Client() as client:
            # Create session
            resp = client.post(
                f"{BSKY_API_BASE}/com.atproto.server.createSession",
                json={
                    "identifier": handle,
                    "password": app_password,
                },
            )
            resp.raise_for_status()
            session = resp.json()

            # Get full profile
            profile_resp = client.get(
                f"{BSKY_API_BASE}/app.bsky.actor.getProfile",
                params={"actor": session["did"]},
                headers={"Authorization": f"Bearer {session['accessJwt']}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        return OAuthResult(
            platform_user_id=session["did"],
            username=session.get("handle", handle),
            display_name=profile.get("displayName", session.get("handle", "")),
            avatar_url=profile.get("avatar", ""),
            access_token=session["accessJwt"],
            refresh_token=session["refreshJwt"],
            token_expires_at=None,  # AT Protocol sessions need refresh
            token_scope="full",
            metadata={
                "followers_count": profile.get("followersCount", 0),
                "following_count": profile.get("followsCount", 0),
                "posts_count": profile.get("postsCount", 0),
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        with httpx.Client() as client:
            resp = client.post(
                f"{BSKY_API_BASE}/com.atproto.server.refreshSession",
                headers={"Authorization": f"Bearer {refresh_token}"},
            )
            resp.raise_for_status()
            session = resp.json()

        return {
            "access_token": session["accessJwt"],
            "refresh_token": session["refreshJwt"],
        }

    def _upload_image(self, access_token: str, image_url: str) -> Optional[dict]:
        """Download an image and upload it as a blob to Bluesky."""
        try:
            with httpx.Client(timeout=30) as client:
                # Download image
                img_resp = client.get(image_url)
                img_resp.raise_for_status()
                image_data = img_resp.content
                content_type = img_resp.headers.get("content-type", "image/jpeg")

                # Upload blob
                blob_resp = client.post(
                    f"{BSKY_API_BASE}/com.atproto.repo.uploadBlob",
                    content=image_data,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": content_type,
                    },
                )
                blob_resp.raise_for_status()
                return blob_resp.json().get("blob")
        except Exception as e:
            logger.error("Bluesky image upload failed: %s", e)
            return None

    def _parse_facets(self, text: str) -> list[dict]:
        """
        Parse mentions (@handle) and URLs into Bluesky facets for rich text.
        """
        import re
        facets = []

        # Parse URLs
        url_pattern = re.compile(r'https?://[^\s<>\])"]+')
        for match in url_pattern.finditer(text):
            facets.append({
                "index": {
                    "byteStart": len(text[:match.start()].encode("utf-8")),
                    "byteEnd": len(text[:match.end()].encode("utf-8")),
                },
                "features": [{
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": match.group(),
                }],
            })

        # Parse mentions
        mention_pattern = re.compile(r'@([a-zA-Z0-9._-]+(?:\.[a-zA-Z0-9._-]+)*)')
        for match in mention_pattern.finditer(text):
            handle = match.group(1)
            # Resolve handle to DID
            try:
                with httpx.Client() as client:
                    resp = client.get(
                        f"{BSKY_API_BASE}/com.atproto.identity.resolveHandle",
                        params={"handle": handle},
                    )
                    if resp.status_code == 200:
                        did = resp.json().get("did", "")
                        facets.append({
                            "index": {
                                "byteStart": len(text[:match.start()].encode("utf-8")),
                                "byteEnd": len(text[:match.end()].encode("utf-8")),
                            },
                            "features": [{
                                "$type": "app.bsky.richtext.facet#mention",
                                "did": did,
                            }],
                        })
            except Exception:
                pass  # Skip unresolvable mentions

        # Parse hashtags
        tag_pattern = re.compile(r'#(\w+)')
        for match in tag_pattern.finditer(text):
            facets.append({
                "index": {
                    "byteStart": len(text[:match.start()].encode("utf-8")),
                    "byteEnd": len(text[:match.end()].encode("utf-8")),
                },
                "features": [{
                    "$type": "app.bsky.richtext.facet#tag",
                    "tag": match.group(1),
                }],
            })

        return facets

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Create a post on Bluesky.
        Supports text, text + images (up to 4), and rich text (URLs, mentions, hashtags).
        """
        # Bluesky posts max 300 chars (grapheme clusters)
        if len(content) > 300:
            content = content[:297] + "..."

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        record = {
            "$type": "app.bsky.feed.post",
            "text": content,
            "createdAt": now,
        }

        # Parse rich text facets
        facets = self._parse_facets(content)
        if facets:
            record["facets"] = facets

        # Upload images (up to 4)
        if media_urls:
            images = []
            for url in media_urls[:4]:
                blob = self._upload_image(access_token, url)
                if blob:
                    images.append({
                        "alt": content[:300],
                        "image": blob,
                    })
            if images:
                record["embed"] = {
                    "$type": "app.bsky.embed.images",
                    "images": images,
                }

        # Get the DID from the access token (we stored it as platform_user_id)
        repo = kwargs.get("did", "")
        if not repo:
            # Resolve from session
            try:
                with httpx.Client() as client:
                    session_resp = client.get(
                        f"{BSKY_API_BASE}/com.atproto.server.getSession",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    session_resp.raise_for_status()
                    repo = session_resp.json()["did"]
            except Exception as e:
                return PublishResult(success=False, error=f"Could not resolve DID: {e}")

        try:
            with httpx.Client() as client:
                resp = client.post(
                    f"{BSKY_API_BASE}/com.atproto.repo.createRecord",
                    json={
                        "repo": repo,
                        "collection": "app.bsky.feed.post",
                        "record": record,
                    },
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                uri = data.get("uri", "")
                # Convert AT URI to web URL
                # at://did:plc:xxx/app.bsky.feed.post/yyy → https://bsky.app/profile/did:plc:xxx/post/yyy
                parts = uri.replace("at://", "").split("/")
                if len(parts) >= 3:
                    web_url = f"https://bsky.app/profile/{parts[0]}/post/{parts[2]}"
                else:
                    web_url = ""

                return PublishResult(
                    success=True,
                    platform_post_id=uri,
                    url=web_url,
                )
        except httpx.HTTPStatusError as e:
            logger.error("Bluesky publish failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """
        Get metrics for a Bluesky post.
        platform_post_id is the AT URI.
        """
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{BSKY_API_BASE}/app.bsky.feed.getPostThread",
                    params={"uri": platform_post_id, "depth": 0},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                thread = resp.json().get("thread", {})
                post = thread.get("post", {})
                return PostMetrics(
                    likes=post.get("likeCount", 0),
                    comments=post.get("replyCount", 0),
                    shares=post.get("repostCount", 0) + post.get("quoteCount", 0),
                )
        except httpx.HTTPStatusError as e:
            logger.error("Bluesky metrics failed: %s", e.response.text)
            return PostMetrics()

    def get_mentions(self, access_token: str, since_id: Optional[str] = None) -> list[dict]:
        try:
            with httpx.Client() as client:
                params = {"limit": 25}
                resp = client.get(
                    f"{BSKY_API_BASE}/app.bsky.notification.listNotifications",
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                mentions = []
                for notif in resp.json().get("notifications", []):
                    if notif.get("reason") in ("mention", "reply"):
                        record = notif.get("record", {})
                        mentions.append({
                            "id": notif.get("uri", ""),
                            "author": notif.get("author", {}).get("handle", ""),
                            "text": record.get("text", ""),
                            "created_at": record.get("createdAt", ""),
                            "type": notif.get("reason", "mention"),
                        })
                return mentions
        except httpx.HTTPStatusError as e:
            logger.error("Bluesky mentions failed: %s", e.response.text)
            return []


# Auto-register
register_provider(BlueskyProvider())
