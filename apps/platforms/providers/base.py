"""
BaseProvider — Abstract base class for all social platform providers.

Every platform (Twitter, LinkedIn, etc.) implements this interface.
The provider handles:
  1. OAuth flow (get_auth_url, handle_callback)
  2. Token management (refresh_token)
  3. Publishing (publish_post)
  4. Reading metrics (get_post_metrics)
  5. Reading engagement (get_mentions, get_comments)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class PlatformAuthError(Exception):
    """Raised when a platform API returns an authentication/permission error.

    This signals that the stored access token is expired, revoked, or missing
    required permissions. The caller should mark the account for
    re-authentication rather than retrying.
    """


@dataclass
class OAuthResult:
    """Result of an OAuth callback."""
    platform_user_id: str
    username: str
    display_name: str = ""
    avatar_url: str = ""
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: Optional[datetime] = None
    token_scope: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class PublishResult:
    """Result of publishing a post."""
    success: bool
    platform_post_id: str = ""
    url: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class PostMetrics:
    """Metrics for a published post."""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    impressions: int = 0
    reach: int = 0
    clicks: int = 0
    saves: int = 0
    metadata: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """
    Abstract base class for all social platform providers.

    Each platform subclass must implement:
    - platform_name: class attribute
    - get_auth_url(): Generate OAuth authorization URL
    - handle_callback(): Exchange OAuth code for tokens + user info
    - refresh_access_token(): Refresh an expired access token
    - publish_post(): Publish content to the platform
    - get_post_metrics(): Fetch metrics for a published post
    """

    platform_name: str = ""

    @abstractmethod
    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        """
        Generate the OAuth authorization URL to redirect the user to.
        Args:
            state: CSRF token / state string to verify on callback
            redirect_uri: The callback URL the platform will redirect to
        Returns:
            Full authorization URL
        """
        ...

    @abstractmethod
    def handle_callback(self, code: str, redirect_uri: str) -> OAuthResult:
        """
        Exchange the authorization code for tokens and fetch user profile.
        Args:
            code: The authorization code from the OAuth callback
            redirect_uri: Must match the redirect_uri used in get_auth_url
        Returns:
            OAuthResult with tokens and user info
        """
        ...

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Refresh an expired access token.
        Args:
            refresh_token: The stored refresh token
        Returns:
            Dict with keys: access_token, refresh_token (optional), expires_at (optional)
        """
        ...

    @abstractmethod
    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        Publish a post to the platform.
        Args:
            access_token: Valid access token
            content: The text content of the post
            media_urls: Optional list of media URLs to attach
            **kwargs: Platform-specific options (e.g., thread for Twitter)
        Returns:
            PublishResult with success status and post ID/URL
        """
        ...

    @abstractmethod
    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """
        Fetch engagement metrics for a published post.
        Args:
            access_token: Valid access token
            platform_post_id: The platform's post ID
        Returns:
            PostMetrics dataclass
        """
        ...

    def get_mentions(self, access_token: str, since_id: Optional[str] = None) -> list[dict]:
        """
        Fetch recent mentions/comments. Override in providers that support it.
        Returns list of dicts with keys: id, author, text, created_at, type
        """
        return []

    def get_comments(self, access_token: str, post_id: str, **kwargs) -> list[dict]:
        """
        Fetch comments on a specific post.
        Returns list of dicts with keys: id, author_id, author_name, text, created_at
        """
        return []

    def reply_to_comment(self, access_token: str, comment_id: str,
                         message: str, **kwargs) -> dict:
        """
        Reply to a comment. Returns dict with reply id or error.
        """
        return {}

    def get_messages(self, access_token: str, **kwargs) -> list[dict]:
        """
        Fetch direct messages / inbox conversations.
        Returns list of dicts with keys: id, sender_id, sender_name, text, created_at
        """
        return []

    def send_message(self, access_token: str, recipient_id: str,
                     message: str, **kwargs) -> dict:
        """
        Send a direct message / reply to a conversation.
        Returns dict with message id or error.
        """
        return {}

    def get_account_insights(self, access_token: str, **kwargs) -> dict:
        """
        Fetch account-level insights (follower growth, reach, demographics).
        Returns dict of metric_name: value.
        """
        return {}

    def delete_post(self, access_token: str, platform_post_id: str, **kwargs) -> bool:
        """
        Delete a published post. Returns True if successful.
        """
        return False

    def update_post(self, access_token: str, platform_post_id: str,
                    content: str, **kwargs) -> PublishResult:
        """
        Update/edit a published post. Returns PublishResult.
        """
        return PublishResult(success=False, error="Not supported by this provider")

    def react_to_post(self, access_token: str, post_id: str,
                      reaction: str = "LIKE", **kwargs) -> dict:
        """
        React to a post (like, celebrate, etc.). Returns dict with result.
        """
        return {}

    def get_own_posts(self, access_token: str, count: int = 20, **kwargs) -> list[dict]:
        """
        Fetch the user's own posts/feed history.
        Returns list of dicts with keys: id, text, created_at, metrics, url
        """
        return []

    def validate_token(self, access_token: str) -> bool:
        """
        Check if an access token is still valid. Default: try a lightweight API call.
        Override per-provider for a proper validation endpoint.
        """
        try:
            self.get_user_info(access_token)
            return True
        except Exception:
            return False

    def get_user_info(self, access_token: str) -> dict:
        """
        Fetch current user info. Useful for token validation and profile sync.
        Override per-provider.
        """
        return {}

    def revoke_token(self, access_token: str) -> bool:
        """
        Revoke an access token on the platform side. Override per-provider.
        Returns True if revocation was successful.
        """
        return False
