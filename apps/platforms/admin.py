from django.contrib import admin

from apps.platforms.models import SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "username", "is_active", "connected_at"]
    list_filter = ["platform", "is_active"]
    search_fields = ["username", "user__email"]
