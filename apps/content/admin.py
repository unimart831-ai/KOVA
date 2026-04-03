from django.contrib import admin

from apps.content.models import ABTest, Post, MediaAttachment


class MediaInline(admin.TabularInline):
    model = MediaAttachment
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [MediaInline]
    list_display = ["user", "social_account", "status", "content_type", "variant_label", "scheduled_at", "created_at"]
    list_filter = ["status", "content_type", "social_account__platform", "ab_test"]
    search_fields = ["content_text", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ABTest)
class ABTestAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "social_account", "status", "variant_count", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
