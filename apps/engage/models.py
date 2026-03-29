import uuid
from django.conf import settings
from django.db import models


class Interaction(models.Model):
    """Tracked comment/reply/DM from the platform."""

    class InteractionType(models.TextChoices):
        COMMENT = "comment", "Comment"
        REPLY = "reply", "Reply"
        MENTION = "mention", "Mention"
        DM = "dm", "Direct Message"

    class Status(models.TextChoices):
        NEW = "new", "New"
        AI_REPLIED = "ai_replied", "AI Replied"
        USER_REPLIED = "user_replied", "User Replied"
        IGNORED = "ignored", "Ignored"
        FLAGGED = "flagged", "Flagged"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interactions")
    social_account = models.ForeignKey("platforms.SocialAccount", on_delete=models.CASCADE, related_name="interactions")
    post = models.ForeignKey("content.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="interactions")
    interaction_type = models.CharField(max_length=20, choices=InteractionType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    author_name = models.CharField(max_length=255)
    author_username = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    ai_suggested_reply = models.TextField(blank=True)
    ai_reply_sent = models.TextField(blank=True)
    platform_interaction_id = models.CharField(max_length=255, blank=True)
    sentiment = models.CharField(max_length=20, blank=True)  # positive, neutral, negative
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_interaction_type_display()} from {self.author_name}"
