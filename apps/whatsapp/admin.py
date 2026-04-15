from django.contrib import admin

from apps.whatsapp.models import (
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
    WhatsAppBroadcast,
)


@admin.register(WhatsAppConversation)
class WhatsAppConversationAdmin(admin.ModelAdmin):
    list_display = ("contact_name", "contact_phone_display", "social_account", "status", "language", "last_message_at")
    list_filter = ("status", "language", "ai_handling")
    search_fields = ("contact_name",)
    readonly_fields = ("id", "created_at")

    def contact_phone_display(self, obj):
        return obj.contact_phone[-4:].rjust(len(obj.contact_phone), "*") if obj.contact_phone else ""
    contact_phone_display.short_description = "Phone"


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "direction", "message_type", "status", "is_ai_generated", "created_at")
    list_filter = ("direction", "message_type", "status", "is_ai_generated")
    readonly_fields = ("id", "created_at")


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "language", "status", "created_by_ai", "created_at")
    list_filter = ("status", "category", "language", "created_by_ai")
    search_fields = ("name", "body_text")
    readonly_fields = ("id", "created_at")


@admin.register(WhatsAppBroadcast)
class WhatsAppBroadcastAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "total_recipients", "delivered_count", "read_count", "scheduled_at")
    list_filter = ("status",)
    readonly_fields = ("id", "created_at")
