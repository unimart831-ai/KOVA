import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """In-app notification for user actions and agent events."""

    class NotificationType(models.TextChoices):
        POST_PUBLISHED = "post_published", "Post Published"
        PUBLISH_FAILED = "publish_failed", "Publish Failed"
        POSTS_GENERATED = "posts_generated", "Posts Generated"
        AGENT_ACTION = "agent_action", "Agent Action"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=30, choices=NotificationType.choices, default=NotificationType.SYSTEM
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    related_post = models.ForeignKey(
        "content.Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.message[:60]}"

    @classmethod
    def create_for_user(cls, user, notification_type, message, related_post=None):
        """Helper to create a notification."""
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            message=message,
            related_post=related_post,
        )

    @classmethod
    def unread_count(cls, user):
        return cls.objects.filter(user=user, is_read=False).count()

    @classmethod
    def mark_all_read(cls, user):
        cls.objects.filter(user=user, is_read=False).update(is_read=True)
