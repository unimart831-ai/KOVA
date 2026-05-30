import logging
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.platforms.encryption import EncryptedTokenField

logger = logging.getLogger(__name__)


class SocialAccount(models.Model):
    """A connected social media account."""

    class Platform(models.TextChoices):
        TWITTER = "twitter", "X (Twitter)"
        LINKEDIN = "linkedin", "LinkedIn"
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        TIKTOK = "tiktok", "TikTok"
        YOUTUBE = "youtube", "YouTube"
        PINTEREST = "pinterest", "Pinterest"
        THREADS = "threads", "Threads"
        BLUESKY = "bluesky", "Bluesky"
        WHATSAPP = "whatsapp", "WhatsApp"

    class AccountType(models.TextChoices):
        PERSONAL = "personal", "Personal"
        BUSINESS = "business", "Business"
        CREATOR = "creator", "Creator"
        PAGE = "page", "Page"
        ORGANIZATION = "organization", "Organization"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default="personal",
        help_text="Type of account: personal, business, creator, page, or organization",
    )
    platform_user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=2048, blank=True)
    access_token = EncryptedTokenField(blank=True)
    refresh_token = EncryptedTokenField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_scope = models.TextField(blank=True, help_text="OAuth scopes granted by the user")
    is_active = models.BooleanField(default=True)
    last_error = models.TextField(blank=True, help_text="Last OAuth or API error message")
    last_synced_at = models.DateTimeField(null=True, blank=True, help_text="Last time we successfully called the API")
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ["user", "platform", "platform_user_id"]
        ordering = ["platform", "username"]
        indexes = [
            models.Index(fields=["user", "is_active", "-last_synced_at"]),
            models.Index(fields=["is_active", "token_expires_at"]),
        ]

    def __str__(self):
        type_label = f" ({self.get_account_type_display()})" if self.account_type != "personal" else ""
        return f"{self.get_platform_display()} - @{self.username}{type_label}"

    @property
    def is_organization_account(self):
        return self.account_type in ("business", "page", "organization")

    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at

    @property
    def needs_reauth(self):
        if not self.is_active:
            return True
        if not self.is_token_expired:
            return False
        # Instagram/Facebook can refresh using access_token (fb_exchange_token)
        if self.platform in ("instagram", "facebook") and self.access_token:
            return False
        return not self.refresh_token

    # HTTP status codes that indicate transient (retryable) failures.
    # These should NOT count as strikes — the external service is having issues.
    TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

    def mark_error(self, error_message, status_code=None):
        """
        Record an API error with smart classification.

        Transient errors (429/500/502/503/504): logged but do NOT count as
        strikes. The external service is having issues — not our user's fault.

        Permanent errors (401/403/other): count toward 3-strike deactivation.
        These indicate real auth failures that require user action.

        Args:
            error_message: Human-readable error description
            status_code: HTTP status code (if available) for classification
        """
        meta = self.metadata or {}
        is_transient = status_code in self.TRANSIENT_STATUS_CODES if status_code else False

        if is_transient:
            # Log the transient error but don't count it as a strike
            meta["last_transient_error"] = str(error_message)[:500]
            meta["transient_error_count"] = meta.get("transient_error_count", 0) + 1
            self.metadata = meta
            self.last_error = f"[transient {status_code}] {str(error_message)[:900]}"
            self.save(update_fields=["last_error", "metadata", "updated_at"])
            return

        # Permanent error — counts as a strike
        consecutive = meta.get("consecutive_errors", 0) + 1
        meta["consecutive_errors"] = consecutive
        meta["transient_error_count"] = 0  # Reset transient counter on real error
        self.metadata = meta
        self.last_error = str(error_message)[:1000]
        fields = ["last_error", "metadata", "updated_at"]

        if consecutive >= 3:
            # 3 strikes — deactivate and notify
            was_active = self.is_active
            self.is_active = False
            fields.append("is_active")
            if was_active:
                logger.error(
                    "SocialAccount deactivated after 3 strikes: "
                    "account=%s platform=%s user=%s last_error=%s",
                    self.id, self.platform, self.user_id,
                    str(error_message)[:300],
                )
        else:
            logger.warning(
                "SocialAccount strike %d/3: account=%s platform=%s user=%s status=%s error=%s",
                consecutive, self.id, self.platform, self.user_id,
                status_code, str(error_message)[:300],
            )

        self.save(update_fields=fields)

    def clear_errors(self):
        """Reset error counter (call after any successful API call)."""
        meta = self.metadata or {}
        if meta.get("consecutive_errors"):
            meta["consecutive_errors"] = 0
            self.metadata = meta
            self.last_error = ""
            self.save(update_fields=["last_error", "metadata", "updated_at"])

    def mark_synced(self):
        self.last_synced_at = timezone.now()
        self.last_error = ""
        meta = self.metadata or {}
        meta["consecutive_errors"] = 0
        self.metadata = meta
        self.save(update_fields=["last_synced_at", "last_error", "metadata", "updated_at"])
