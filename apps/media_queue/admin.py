from django.contrib import admin

from .models import MediaQueue, QueueItem


class QueueItemInline(admin.TabularInline):
    model = QueueItem
    extra = 0
    fields = ("order", "status", "caption", "scheduled_for", "published_at")
    readonly_fields = ("published_at",)
    ordering = ("order",)


@admin.register(MediaQueue)
class MediaQueueAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "social_account", "is_active", "rhythm_type", "queued_count", "created_at")
    list_filter = ("is_active", "rhythm_type")
    search_fields = ("name", "user__email")
    inlines = [QueueItemInline]

    def queued_count(self, obj):
        return obj.queued_count
    queued_count.short_description = "Queued"


@admin.register(QueueItem)
class QueueItemAdmin(admin.ModelAdmin):
    list_display = ("queue", "order", "status", "scheduled_for", "published_at")
    list_filter = ("status",)
    ordering = ("queue", "order")
