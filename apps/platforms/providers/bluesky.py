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

    # ─────────────────────────────────────────────────────────────────────
    # Engagement methods
    # ─────────────────────────────────────────────────────────────────────

    def _resolve_did(self, access_token: str) -> str:
        """Resolve the DID for the authenticated user from the active session."""
        with httpx.Client() as client:
            resp = client.get(
                f"{BSKY_API_BASE}/com.atproto.server.getSession",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()["did"]

    def _get_post_ref(self, access_token: str, uri: str) -> Optional[dict]:
        """
        Fetch a post's URI and CID to build a reply reference.
        Returns {"uri": ..., "cid": ...} or None on failure.
        """
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{BSKY_API_BASE}/app.bsky.feed.getPostThread",
                    params={"uri": uri, "depth": 0},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                post = resp.json().get("thread", {}).get("post", {})
                return {"uri": post["uri"], "cid": post["cid"]}
        except Exception as e:
            logger.error("Bluesky _get_post_ref failed for %s: %s", uri, e)
            return None

    def _get_root_ref(self, access_token: str, uri: str) -> Optional[dict]:
        """
        Walk up the reply chain to find the root post reference.
        If the post has no parent (is itself the root), returns its own ref.
        """
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{BSKY_API_BASE}/app.bsky.feed.getPostThread",
                    params={"uri": uri, "depth": 0},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                thread = resp.json().get("thread", {})
                post = thread.get("post", {})
                record = post.get("record", {})

                reply_info = record.get("reply")
                if reply_info and reply_info.get("root"):
                    return {
                        "uri": reply_info["root"]["uri"],
                        "cid": reply_info["root"]["cid"],
                    }
                # This post is itself the root
                return {"uri": post["uri"], "cid": post["cid"]}
        except Exception as e:
            logger.error("Bluesky _get_root_ref failed for %s: %s", uri, e)
            return None

    def get_comments(self, access_token: str, post_id: str) -> list[dict]:
        """
        Fetch direct replies (comments) on a post.
        post_id: AT URI (e.g. at://did:plc:xxx/app.bsky.feed.post/yyy)
        """
        try:
            with httpx.Client() as client:
                resp = client.get(
                    f"{BSKY_API_BASE}/app.bsky.feed.getPostThread",
                    params={"uri": post_id, "depth": 1},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                thread = resp.json().get("thread", {})
                replies = thread.get("replies", [])

                comments = []
                for reply_thread in replies:
                    post = reply_thread.get("post", {})
                    author = post.get("author", {})
                    record = post.get("record", {})
                    comments.append({
                        "id": post.get("uri", ""),
                        "author_name": author.get("displayName") or author.get("handle", ""),
                        "author_id": author.get("did", ""),
                        "text": record.get("text", ""),
                        "created_at": record.get("createdAt", ""),
                    })
                return comments
        except httpx.HTTPStatusError as e:
            logger.error("Bluesky get_comments failed: %s", e.response.text)
            return []
        except Exception as e:
            logger.error("Bluesky get_comments error: %s", e)
            return []

    def reply_to_comment(self, access_token: str, comment_id: str, text: str) -> bool:
        """
        Reply to a specific comment/post on Bluesky.
        comment_id: AT URI of the comment being replied to.
        Returns True on success, False on failure.
        """
        try:
            repo = self._resolve_did(access_token)

            parent_ref = self._get_post_ref(access_token, comment_id)
            if not parent_ref:
                logger.error("reply_to_comment: could not resolve parent ref for %s", comment_id)
                return False

            root_ref = self._get_root_ref(access_token, comment_id)
            if not root_ref:
                logger.error("reply_to_comment: could not resolve root ref for %s", comment_id)
                return False

            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            record = {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
                "reply": {
                    "root": root_ref,
                    "parent": parent_ref,
                },
            }

            facets = self._parse_facets(text)
            if facets:
                record["facets"] = facets

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
                return True
        except httpx.HTTPStatusError as e:
            logger.error("Bluesky reply_to_comment failed: %s", e.response.text)
            return False
        except Exception as e:
            logger.error("Bluesky reply_to_comment error: %s", e)
            return False

    def post_comment(self, access_token: str, post_id: str, text: str) -> str:
        """
        Post a top-level reply to a post (the parent IS the root).
        post_id: AT URI of the post being replied to.
        Returns the AT URI of the created reply, or empty string on failure.
        """
        try:
            repo = self._resolve_did(access_token)

            post_ref = self._get_post_ref(access_token, post_id)
            if not post_ref:
                logger.error("post_comment: could not resolve post ref for %s", post_id)
                return ""

            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            record = {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
                "reply": {
                    "root": post_ref,
                    "parent": post_ref,
                },
            }

            facets = self._parse_facets(text)
            if facets:
                record["facets"] = facets

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
                return resp.json().get("uri", "")
        except httpx.HTTPStatusError as e:
            logger.error("Bluesky post_comment failed: %s", e.response.text)
            return ""
        except Exception as e:
            logger.error("Bluesky post_comment error: %s", e)
            return ""


# Auto-register
register_provider(BlueskyProvider())
