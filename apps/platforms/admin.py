from django.contrib import admin

from apps.platforms.models import SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "account_type", "username", "is_active", "connected_at"]
    list_filter = ["platform", "account_type", "is_active"]
    search_fields = ["username", "user__email"]
