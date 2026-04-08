"""
LinkedIn Provider — Full LinkedIn REST API integration.

Uses LinkedIn REST Posts API (replaces deprecated UGC API), Images API,
Videos API, Comments API, and Reactions API for complete LinkedIn
integration.

Full capability matrix:
─────────────────────────────────────────────────────────────────────────────
CAPABILITY                           │ API ENDPOINT
─────────────────────────────────────────────────────────────────────────────
Connect via OAuth 2.0                │ OAuth 2.0 3-legged flow
Token refresh                        │ /oauth/v2/accessToken
User profile                         │ /v2/userinfo (OpenID Connect)
Publish text post                    │ POST /rest/posts
Publish image post (single)          │ Images API + Posts API
Publish multi-image post (up to 9)   │ Images API + Posts API
Publish video post                   │ Videos API + Posts API
Publish article/link post            │ Posts API (content.article)
Delete post                          │ DELETE /rest/posts/{urn}
Edit/update post                     │ POST /rest/posts/{urn} PARTIAL_UPDATE
Get own posts                        │ GET /rest/posts?q=author
Get post metrics                     │ Social Metadata / socialActions API
Get comments on post                 │ GET /rest/socialActions/{urn}/comments
Reply to comment                     │ POST /rest/socialActions/{urn}/comments
React to post/comment                │ POST /rest/reactions
Validate token                       │ /v2/userinfo check
─────────────────────────────────────────────────────────────────────────────

Permissions required:
  openid, profile, w_member_social

API version header: LinkedIn-Version: 202401

Docs:
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/reactions-api
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote, urlencode

import httpx

from django.conf import settings

from apps.platforms.providers.base import (
    BaseProvider, OAuthResult, PostMetrics, PublishResult,
)
from apps.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

# ── API endpoints ────────────────────────────────────────────────────────────
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_REST_BASE = "https://api.linkedin.com/rest"
LINKEDIN_VERSION = "202401"
LINKEDIN_SCOPES = "openid profile w_member_social"
LINKEDIN_ORG_SCOPES = "openid profile w_member_social w_organization_social r_organization_social"


class LinkedInProvider(BaseProvider):
    """Full LinkedIn integration via REST Posts, Images, Videos,
    Comments, and Reactions APIs."""

    platform_name = "linkedin"

    def __init__(self):
        self.client_id = getattr(settings, "LINKEDIN_CLIENT_ID", "")
        self.client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", "")

    # ── Internal helpers ─────────────────────────────────────────────────

    def _rest_headers(self, access_token: str,
                      extra: Optional[dict] = None) -> dict:
        """Standard headers for every LinkedIn REST API call."""
        h = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "Content-Type": "application/json",
        }
        if extra:
            h.update(extra)
        return h

    def _get_author_urn(self, access_token: str, **kwargs) -> str:
        """Resolve the author URN — either a person or organization.

        For organization accounts, returns urn:li:organization:{org_id}.
        For personal accounts, returns urn:li:person:{sub}.

        Checks kwargs → account metadata → /userinfo fallback."""
        if kwargs.get("author_urn"):
            return kwargs["author_urn"]

        account = kwargs.get("account")
        if account and hasattr(account, "metadata") and isinstance(
            account.metadata, dict
        ):
            # Check for organization URN first (Company Page accounts)
            org_id = account.metadata.get("organization_id", "")
            if org_id and getattr(account, "account_type", "") == "organization":
                return f"urn:li:organization:{org_id}"

            sub = account.metadata.get("linkedin_sub", "")
            if sub:
                return f"urn:li:person:{sub}"

        try:
            info = self.get_user_info(access_token)
            sub = info.get("sub", "")
            if sub:
                return f"urn:li:person:{sub}"
        except Exception:
            pass
        return ""

    # ── Media upload helpers ─────────────────────────────────────────────

    def _upload_image(self, access_token: str, author_urn: str,
                      image_url: str) -> Optional[str]:
        """Upload an image via the Images API.
        Flow: initializeUpload → download source → PUT binary → image URN.
        Supports JPG, PNG, GIF up to 36 megapixels."""
        headers = self._rest_headers(access_token)

        with httpx.Client(timeout=60) as client:
            # 1. Initialize upload
            init_resp = client.post(
                f"{LINKEDIN_REST_BASE}/images?action=initializeUpload",
                json={"initializeUploadRequest": {"owner": author_urn}},
                headers=headers,
            )
            init_resp.raise_for_status()
            value = init_resp.json().get("value", {})
            upload_url = value.get("uploadUrl", "")
            image_urn = value.get("image", "")

            if not upload_url or not image_urn:
                logger.error("LinkedIn image init: missing uploadUrl or image URN")
                return None

            # 2. Download source image
            dl = client.get(image_url, follow_redirects=True, timeout=30)
            dl.raise_for_status()
            content_type = dl.headers.get(
                "content-type", "application/octet-stream"
            )

            # 3. PUT binary to LinkedIn's upload URL
            client.put(
                upload_url,
                content=dl.content,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": content_type,
                },
            ).raise_for_status()

            logger.info("LinkedIn image uploaded: %s", image_urn)
            return image_urn

    def _upload_image_bytes(self, access_token: str, author_urn: str,
                            filename: str, image_bytes: bytes,
                            content_type: str = "image/jpeg") -> Optional[str]:
        """Upload image bytes directly via the Images API (no URL download).

        Same flow as _upload_image but skips the download step.
        """
        headers = self._rest_headers(access_token)

        with httpx.Client(timeout=60) as client:
            # 1. Initialize upload
            init_resp = client.post(
                f"{LINKEDIN_REST_BASE}/images?action=initializeUpload",
                json={"initializeUploadRequest": {"owner": author_urn}},
                headers=headers,
            )
            init_resp.raise_for_status()
            value = init_resp.json().get("value", {})
            upload_url = value.get("uploadUrl", "")
            image_urn = value.get("image", "")

            if not upload_url or not image_urn:
                logger.error("LinkedIn image init: missing uploadUrl or image URN")
                return None

            # 2. PUT binary directly (skip download step)
            client.put(
                upload_url,
                content=image_bytes,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": content_type,
                },
            ).raise_for_status()

            logger.info("LinkedIn image uploaded (direct): %s (%d bytes)", image_urn, len(image_bytes))
            return image_urn

    def _upload_video(self, access_token: str, author_urn: str,
                      video_url: str) -> Optional[str]:
        """Upload a video via the Videos API.
        Flow: download source → initializeUpload → upload 4 MB parts
              → finalizeUpload → video URN.
        Supports MP4, 3 s – 30 min, 75 KB – 500 MB."""
        headers = self._rest_headers(access_token)

        with httpx.Client(timeout=120) as client:
            # 1. Download source video
            dl = client.get(video_url, follow_redirects=True, timeout=60)
            dl.raise_for_status()
            vid_bytes = dl.content
            file_size = len(vid_bytes)

            # 2. Initialize upload
            init_resp = client.post(
                f"{LINKEDIN_REST_BASE}/videos?action=initializeUpload",
                json={
                    "initializeUploadRequest": {
                        "owner": author_urn,
                        "fileSizeBytes": file_size,
                    }
                },
                headers=headers,
            )
            init_resp.raise_for_status()
            value = init_resp.json().get("value", {})
            video_urn = value.get("video", "")
            instructions = value.get("uploadInstructions", [])

            if not video_urn or not instructions:
                logger.error(
                    "LinkedIn video init: missing video URN or instructions"
                )
                return None

            # 3. Upload each part and collect ETags
            etags = []
            for instr in instructions:
                chunk = vid_bytes[instr["firstByte"]:instr["lastByte"] + 1]
                up_resp = client.put(
                    instr["uploadUrl"],
                    content=chunk,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/octet-stream",
                    },
                    timeout=60,
                )
                up_resp.raise_for_status()
                etag = up_resp.headers.get("etag", "")
                if etag:
                    etags.append(etag)

            # 4. Finalize
            client.post(
                f"{LINKEDIN_REST_BASE}/videos?action=finalizeUpload",
                json={
                    "finalizeUploadRequest": {
                        "video": video_urn,
                        "uploadToken": "",
                        "uploadedPartIds": etags,
                    }
                },
                headers=headers,
            ).raise_for_status()

            logger.info(
                "LinkedIn video uploaded: %s (%d bytes, %d parts)",
                video_urn, file_size, len(etags),
            )
            return video_urn

    # ── OAuth ────────────────────────────────────────────────────────────

    def get_auth_url(self, state: str, redirect_uri: str,
                     include_org_scopes: bool = False) -> str:
        scopes = LINKEDIN_ORG_SCOPES if include_org_scopes else LINKEDIN_SCOPES
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
        }
        return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"

    def get_organizations(self, access_token: str) -> list[dict]:
        """Fetch LinkedIn Company Pages the user is an admin of.

        Uses the organizationAcls endpoint to find orgs where the
        authenticated user has ADMINISTRATOR role.

        Returns list of dicts with id, name, vanity_name, logo_url."""
        headers = self._rest_headers(access_token)
        try:
            with httpx.Client(timeout=30) as client:
                # Get organization admin roles
                resp = client.get(
                    f"{LINKEDIN_REST_BASE}/organizationAcls",
                    params={
                        "q": "roleAssignee",
                        "role": "ADMINISTRATOR",
                        "projection": "(elements*(organization~(id,localizedName,vanityName,logoV2(original~:playableStreams))))",
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                elements = resp.json().get("elements", [])

                orgs = []
                for el in elements:
                    org_data = el.get("organization~", {})
                    org_urn = el.get("organization", "")
                    org_id = org_urn.split(":")[-1] if org_urn else ""

                    logo_url = ""
                    logo_v2 = org_data.get("logoV2", {})
                    if logo_v2:
                        original = logo_v2.get("original~", {})
                        streams = original.get("elements", [])
                        if streams:
                            logo_url = streams[0].get("identifiers", [{}])[0].get("identifier", "")

                    orgs.append({
                        "id": org_id,
                        "urn": org_urn,
                        "name": org_data.get("localizedName", ""),
                        "vanity_name": org_data.get("vanityName", ""),
                        "logo_url": logo_url,
                    })
                return orgs

        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn get_organizations failed: %s", e.response.text)
            return []
        except Exception as e:
            logger.error("LinkedIn get_organizations error: %s", e)
            return []

    def handle_callback(self, code: str, redirect_uri: str,
                        **kwargs) -> OAuthResult:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        with httpx.Client(timeout=30) as client:
            # Exchange code for tokens
            resp = client.post(
                LINKEDIN_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            tokens = resp.json()

            # Fetch profile via OpenID Connect /userinfo
            profile_resp = client.get(
                LINKEDIN_USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}"
                },
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=tokens["expires_in"]
            )

        user_id = profile.get("sub", "")
        name = profile.get("name", "")

        return OAuthResult(
            platform_user_id=user_id,
            username=name.lower().replace(" ", ""),
            display_name=name,
            avatar_url=profile.get("picture", ""),
            access_token=tokens.get("access_token", ""),
            refresh_token=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
            token_scope=tokens.get("scope", ""),
            metadata={
                "linkedin_sub": user_id,
                "account_type": "personal",
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        with httpx.Client(timeout=30) as client:
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
            result["expires_at"] = datetime.now(timezone.utc) + timedelta(
                seconds=tokens["expires_in"]
            )
        return result

    # ── Publishing ───────────────────────────────────────────────────────

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list] = None,
                     **kwargs) -> PublishResult:
        """
        Publish to LinkedIn using the REST Posts API.

        Supports:
          - Text-only posts
          - Single image (auto-detected from media_urls)
          - Multi-image up to 9 (auto-detected when len > 1)
          - Video (auto-detected from file extension)
          - Article/link (pass article_url kwarg)

        Optional kwargs:
          author_urn, account, post_type,
          article_url, article_title, article_description,
          article_thumbnail, media_title
        """
        author_urn = self._get_author_urn(access_token, **kwargs)
        if not author_urn:
            return PublishResult(
                success=False, error="Could not resolve author URN"
            )

        # ── Determine post type ──────────────────────────────────────
        post_type = kwargs.get("post_type", "text")
        article_url = kwargs.get("article_url")
        media_files = kwargs.get("media_files")  # [(filename, bytes, ctype), ...]

        if article_url:
            post_type = "article"
        elif media_files:
            if len(media_files) > 1:
                post_type = "multi_image"
            else:
                post_type = "image"
        elif media_urls:
            first = media_urls[0].lower().split("?")[0]
            if first.endswith((".mp4", ".mov", ".avi", ".webm")):
                post_type = "video"
            elif len(media_urls) > 1:
                post_type = "multi_image"
            else:
                post_type = "image"

        # ── Upload media before building payload ─────────────────────
        media_content = None

        try:
            if post_type == "image" and media_files:
                urn = self._upload_image_bytes(
                    access_token, author_urn, *media_files[0]
                )
                if not urn:
                    return PublishResult(
                        success=False, error="Image upload failed"
                    )
                media_content = {
                    "media": {
                        "title": kwargs.get("media_title", ""),
                        "id": urn,
                    }
                }

            elif post_type == "multi_image" and media_files:
                images = []
                for fname, data, ctype in media_files[:9]:
                    urn = self._upload_image_bytes(
                        access_token, author_urn, fname, data, ctype
                    )
                    if urn:
                        images.append({"id": urn})
                if not images:
                    return PublishResult(
                        success=False, error="All image uploads failed"
                    )
                media_content = {"multiImage": {"images": images}}

            elif post_type == "image" and media_urls:
                urn = self._upload_image(
                    access_token, author_urn, media_urls[0]
                )
                if not urn:
                    return PublishResult(
                        success=False, error="Image upload failed"
                    )
                media_content = {
                    "media": {
                        "title": kwargs.get("media_title", ""),
                        "id": urn,
                    }
                }

            elif post_type == "multi_image" and media_urls:
                images = []
                for url in media_urls[:9]:
                    urn = self._upload_image(access_token, author_urn, url)
                    if urn:
                        images.append({"id": urn})
                if not images:
                    return PublishResult(
                        success=False, error="All image uploads failed"
                    )
                media_content = {"multiImage": {"images": images}}

            elif post_type == "video" and media_urls:
                urn = self._upload_video(
                    access_token, author_urn, media_urls[0]
                )
                if not urn:
                    return PublishResult(
                        success=False, error="Video upload failed"
                    )
                media_content = {
                    "media": {
                        "title": kwargs.get("media_title", ""),
                        "id": urn,
                    }
                }

            elif post_type == "article" and article_url:
                article = {
                    "source": article_url,
                    "title": kwargs.get("article_title", ""),
                    "description": kwargs.get("article_description", ""),
                }
                thumb_url = kwargs.get("article_thumbnail")
                if thumb_url:
                    thumb_urn = self._upload_image(
                        access_token, author_urn, thumb_url
                    )
                    if thumb_urn:
                        article["thumbnail"] = thumb_urn
                media_content = {"article": article}

        except httpx.HTTPStatusError as e:
            body = e.response.text if hasattr(e, "response") else str(e)
            logger.error("LinkedIn media upload error: %s", body)
            return PublishResult(
                success=False, error=f"Media upload failed: {body}"
            )

        # ── Build and send the post ──────────────────────────────────
        payload = {
            "author": author_urn,
            "commentary": content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }
        if media_content:
            payload["content"] = media_content

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{LINKEDIN_REST_BASE}/posts",
                    json=payload,
                    headers=self._rest_headers(access_token),
                )
                resp.raise_for_status()

                post_urn = resp.headers.get("x-restli-id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=post_urn,
                    url=(
                        f"https://www.linkedin.com/feed/update/{post_urn}/"
                        if post_urn else ""
                    ),
                    metadata={
                        "author_urn": author_urn,
                        "post_type": post_type,
                    },
                )
        except httpx.HTTPStatusError as e:
            body = e.response.text if hasattr(e, "response") else str(e)
            logger.error("LinkedIn publish failed: %s", body)
            return PublishResult(
                success=False, error=f"Publish failed: {body}"
            )

    # ── Post management ──────────────────────────────────────────────────

    def delete_post(self, access_token: str, platform_post_id: str,
                    **kwargs) -> bool:
        """Delete a post. Returns True on 204 No Content."""
        encoded = quote(platform_post_id, safe="")
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.delete(
                    f"{LINKEDIN_REST_BASE}/posts/{encoded}",
                    headers=self._rest_headers(access_token),
                )
                return resp.status_code == 204
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn delete failed: %s", e.response.text)
            return False

    def update_post(self, access_token: str, platform_post_id: str,
                    content: str, **kwargs) -> PublishResult:
        """Edit a post's text via PARTIAL_UPDATE."""
        encoded = quote(platform_post_id, safe="")
        headers = self._rest_headers(
            access_token, extra={"X-RestLi-Method": "PARTIAL_UPDATE"}
        )
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{LINKEDIN_REST_BASE}/posts/{encoded}",
                    json={"patch": {"$set": {"commentary": content}}},
                    headers=headers,
                )
                resp.raise_for_status()
                return PublishResult(
                    success=True,
                    platform_post_id=platform_post_id,
                    url=f"https://www.linkedin.com/feed/update/{platform_post_id}/",
                )
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn update failed: %s", e.response.text)
            return PublishResult(success=False, error=str(e))

    def get_own_posts(self, access_token: str, count: int = 20,
                      **kwargs) -> list:
        """Fetch the authenticated user's recent posts."""
        author_urn = self._get_author_urn(access_token, **kwargs)
        if not author_urn:
            return []

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{LINKEDIN_REST_BASE}/posts",
                    params={
                        "author": author_urn,
                        "q": "author",
                        "count": min(count, 100),
                        "sortBy": "LAST_MODIFIED",
                    },
                    headers=self._rest_headers(access_token),
                )
                resp.raise_for_status()
                elements = resp.json().get("elements", [])

            posts = []
            for el in elements:
                created_ts = el.get("createdAt", 0)
                posts.append({
                    "id": el.get("id", ""),
                    "text": el.get("commentary", ""),
                    "created_at": (
                        datetime.fromtimestamp(
                            created_ts / 1000, tz=timezone.utc
                        ).isoformat()
                        if created_ts else ""
                    ),
                    "visibility": el.get("visibility", ""),
                    "lifecycle_state": el.get("lifecycleState", ""),
                    "url": (
                        f"https://www.linkedin.com/feed/update/"
                        f"{el.get('id', '')}/"
                    ),
                })
            return posts
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn get_own_posts failed: %s", e.response.text)
            return []

    # ── Metrics ──────────────────────────────────────────────────────────

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """Fetch engagement metrics for a post.
        Tries socialMetadata first, falls back to socialActions."""
        headers = self._rest_headers(access_token)
        encoded = quote(platform_post_id, safe="")
        likes = comments = shares = 0

        try:
            with httpx.Client(timeout=30) as client:
                # Try socialMetadata first (aggregate counts)
                resp = client.get(
                    f"{LINKEDIN_REST_BASE}/socialMetadata/{encoded}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    likes = (
                        data.get("reactionSummary", {}).get("totalCount", 0)
                        or data.get("totalReactionCount", 0)
                    )
                    comments = data.get("totalCommentCount", 0)
                    shares = data.get("totalShareCount", 0)
                    return PostMetrics(
                        likes=likes, comments=comments, shares=shares
                    )

                # Fallback: socialActions (likesSummary/commentsSummary)
                resp2 = client.get(
                    f"{LINKEDIN_REST_BASE}/socialActions/{encoded}",
                    headers=headers,
                )
                if resp2.status_code == 200:
                    data = resp2.json()
                    likes = data.get("likesSummary", {}).get(
                        "totalLikes", 0
                    )
                    comments = data.get("commentsSummary", {}).get(
                        "totalFirstLevelComments", 0
                    )
        except Exception as e:
            logger.warning("LinkedIn metrics fetch failed: %s", e)

        return PostMetrics(likes=likes, comments=comments, shares=shares)

    # ── Comments & engagement ────────────────────────────────────────────

    def get_comments(self, access_token: str, post_id: str,
                     **kwargs) -> list:
        """Fetch comments on a post.
        post_id: activity URN (urn:li:activity:123…)"""
        encoded = quote(post_id, safe="")
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{LINKEDIN_REST_BASE}/socialActions/{encoded}/comments",
                    headers=self._rest_headers(access_token),
                )
                resp.raise_for_status()

            result = []
            for c in resp.json().get("elements", []):
                created_ts = c.get("created", {}).get("time", 0)
                result.append({
                    "id": c.get("id", ""),
                    "comment_urn": c.get("commentUrn", ""),
                    "author_id": c.get("actor", ""),
                    "author_name": "",
                    "text": c.get("message", {}).get("text", ""),
                    "created_at": (
                        datetime.fromtimestamp(
                            created_ts / 1000, tz=timezone.utc
                        ).isoformat()
                        if created_ts else ""
                    ),
                    "likes": c.get("likesSummary", {}).get("totalLikes", 0),
                    "parent_comment": c.get("parentComment", ""),
                })
            return result
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn get_comments failed: %s", e.response.text)
            return []

    def reply_to_comment(self, access_token: str, comment_id: str,
                         message: str, **kwargs) -> dict:
        """Reply to a comment on a LinkedIn post.

        Args:
            comment_id: Parent comment URN
                (e.g. urn:li:comment:(urn:li:activity:123,456))
            message: Reply text
            **kwargs: post_id (the activity URN), account
        """
        author_urn = self._get_author_urn(access_token, **kwargs)
        post_id = kwargs.get("post_id", "")

        # Extract post_id from composite comment URN if not provided
        if not post_id and "urn:li:activity:" in comment_id:
            try:
                inner = comment_id.split("(", 1)[1].rsplit(",", 1)[0]
                if inner.startswith("urn:li:activity:"):
                    post_id = inner
            except (IndexError, ValueError):
                pass

        if not post_id:
            return {
                "error": "post_id is required to reply to a LinkedIn comment"
            }

        encoded_post = quote(post_id, safe="")
        payload = {
            "actor": author_urn,
            "object": post_id,
            "message": {"text": message},
            "parentComment": comment_id,
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{LINKEDIN_REST_BASE}/socialActions/"
                    f"{encoded_post}/comments",
                    json=payload,
                    headers=self._rest_headers(access_token),
                )
                resp.raise_for_status()
                return {
                    "id": resp.headers.get("x-restli-id", ""),
                    "success": True,
                }
        except httpx.HTTPStatusError as e:
            logger.error(
                "LinkedIn reply_to_comment failed: %s", e.response.text
            )
            return {"error": str(e)}

    # ── Reactions ────────────────────────────────────────────────────────

    def react_to_post(self, access_token: str, post_id: str,
                      reaction: str = "LIKE", **kwargs) -> dict:
        """React to a LinkedIn post or comment.

        Reaction types:
          LIKE, PRAISE (Celebrate), EMPATHY (Love),
          INTEREST (Insightful), APPRECIATION (Support),
          ENTERTAINMENT (Funny)
        """
        author_urn = self._get_author_urn(access_token, **kwargs)
        encoded_actor = quote(author_urn, safe="")

        valid = {
            "LIKE", "PRAISE", "EMPATHY", "INTEREST",
            "APPRECIATION", "ENTERTAINMENT",
        }
        reaction = reaction.upper()
        if reaction not in valid:
            return {
                "error": f"Invalid reaction. Valid: {', '.join(sorted(valid))}"
            }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{LINKEDIN_REST_BASE}/reactions"
                    f"?actor={encoded_actor}",
                    json={"root": post_id, "reactionType": reaction},
                    headers=self._rest_headers(access_token),
                )
                resp.raise_for_status()
                return {"success": True, "reaction": reaction}
        except httpx.HTTPStatusError as e:
            logger.error("LinkedIn react_to_post failed: %s", e.response.text)
            return {"error": str(e)}

    # ── User / token management ──────────────────────────────────────────

    def get_user_info(self, access_token: str) -> dict:
        """Fetch current user profile via OpenID Connect /userinfo."""
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                LINKEDIN_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()

    def validate_token(self, access_token: str) -> bool:
        """Check token validity with a lightweight /userinfo call."""
        try:
            info = self.get_user_info(access_token)
            return bool(info.get("sub"))
        except Exception:
            return False

    def revoke_token(self, access_token: str) -> bool:
        """LinkedIn does not provide a public token revocation endpoint."""
        return False


# ── Auto-register ────────────────────────────────────────────────────────────
register_provider(LinkedInProvider())
