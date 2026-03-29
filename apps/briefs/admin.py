from django.contrib import admin

from apps.briefs.models import DailyBrief


@admin.register(DailyBrief)
class DailyBriefAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "posts_pending", "is_read", "created_at"]
    list_filter = ["is_read", "date"]
    search_fields = ["user__email"]
