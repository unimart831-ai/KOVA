import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    platform_user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    access_token = models.TextField(blank=True)  # TODO: migrate to EncryptedTextField (django-fernet-fields-v2)
    refresh_token = models.TextField(blank=True)  # TODO: migrate to EncryptedTextField (django-fernet-fields-v2)
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

    def __str__(self):
        return f"{self.get_platform_display()} - @{self.username}"

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
