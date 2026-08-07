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
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["user", "notification_type", "-created_at"]),
        ]

    @classmethod
    def create_for_user(cls, user, notification_type, message, related_post=None):
        """Create a notification, respecting user preferences.
        Also pushes a real-time WebSocket event to the user's browser.
        """
        if notification_type != cls.NotificationType.SYSTEM:
            prefs = NotificationPreference.for_user(user)
            if not prefs.is_enabled(notification_type):
                return None
        notif = cls.objects.create(
            user=user,
            notification_type=notification_type,
            message=message,
            related_post=related_post,
        )
        try:
            from apps.messaging.notifications.realtime import send_user_event
            send_user_event(user.pk, "notification", {
                "message": message,
                "level": "error" if notification_type == cls.NotificationType.PUBLISH_FAILED else "info",
                "count": cls.unread_count(user),
                "notification_type": notification_type,
            })
        except Exception:
            pass
        return notif

    @classmethod
    def unread_count(cls, user):
        return cls.objects.filter(user=user, is_read=False).count()

    @classmethod
    def mark_all_read(cls, user):
        cls.objects.filter(user=user, is_read=False).update(is_read=True)


class NotificationPreference(models.Model):
    """Per-user notification preferences. One row per user, auto-created."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_prefs",
    )
    post_published = models.BooleanField(default=True, help_text="Notify when a post is published")
    publish_failed = models.BooleanField(default=True, help_text="Notify when publishing fails")
    posts_generated = models.BooleanField(default=True, help_text="Notify when new posts are generated")
    agent_action = models.BooleanField(default=True, help_text="Notify when agents take actions")

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"NotificationPreference({self.user})"

    def is_enabled(self, notification_type):
        """Check if a notification type is enabled for this user."""
        field_map = {
            Notification.NotificationType.POST_PUBLISHED: self.post_published,
            Notification.NotificationType.PUBLISH_FAILED: self.publish_failed,
            Notification.NotificationType.POSTS_GENERATED: self.posts_generated,
            Notification.NotificationType.AGENT_ACTION: self.agent_action,
        }
        return field_map.get(notification_type, True)

    @classmethod
    def for_user(cls, user):
        """Get or create preferences for a user."""
        prefs, _ = cls.objects.get_or_create(user=user)
        return prefs
