from django.contrib import admin

from apps.content.models import Post, MediaAttachment


class MediaInline(admin.TabularInline):
    model = MediaAttachment
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [MediaInline]
    list_display = ["user", "social_account", "status", "content_type", "scheduled_at", "created_at"]
    list_filter = ["status", "content_type", "social_account__platform"]
    search_fields = ["content_text", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
