from django.contrib import admin

from apps.create.briefs.models import BriefWhatsAppLog, DailyBrief


@admin.register(DailyBrief)
class DailyBriefAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "posts_pending", "kova_score", "is_read", "created_at"]
    list_filter = ["is_read", "date"]
    search_fields = ["user__email"]


@admin.register(BriefWhatsAppLog)
class BriefWhatsAppLogAdmin(admin.ModelAdmin):
    list_display = ["user", "command", "success", "wa_id", "created_at"]
    list_filter = ["success", "command", "created_at"]
    search_fields = ["user__email", "wa_id", "inbound_text"]
    readonly_fields = ["created_at"]
