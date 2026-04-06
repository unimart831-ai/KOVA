import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.platforms.encryption import EncryptedTokenField


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
    avatar_url = models.URLField(blank=True)
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
        return not self.is_active or (self.is_token_expired and not self.refresh_token)

    def mark_error(self, error_message):
        self.last_error = str(error_message)[:1000]
        self.is_active = False
        self.save(update_fields=["last_error", "is_active", "updated_at"])

    def mark_synced(self):
        self.last_synced_at = timezone.now()
        self.last_error = ""
        self.save(update_fields=["last_synced_at", "last_error", "updated_at"])
