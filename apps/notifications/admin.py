from django.contrib import admin

from apps.notifications.models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["user__email", "message"]
    readonly_fields = ["id", "created_at"]
    raw_id_fields = ["user", "related_post"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "post_published", "publish_failed", "posts_generated", "agent_action"]
    raw_id_fields = ["user"]
