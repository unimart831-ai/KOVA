from django.contrib import admin

from apps.messaging.whatsapp.models import (
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
    WhatsAppBroadcast,
    StatusContent,
    StatusTemplate,
    BroadcastSequence,
    BroadcastSequenceStep,
    SequenceEnrollment,
    WhatsAppAnalytics,
    WeeklyDigest,
    WhatsAppChannel,
    ChannelPost,
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


@admin.register(StatusContent)
class StatusContentAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "state", "scheduled_for", "ai_generated", "created_at")
    list_filter = ("state", "category", "ai_generated")
    search_fields = ("text",)
    readonly_fields = ("id", "created_at")


@admin.register(StatusTemplate)
class StatusTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "usage_count")
    list_filter = ("category", "is_active")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at")


@admin.register(BroadcastSequence)
class BroadcastSequenceAdmin(admin.ModelAdmin):
    list_display = ("name", "sequence_type", "status", "enrolled_count", "completed_count")
    list_filter = ("status", "sequence_type")
    readonly_fields = ("id", "created_at")


@admin.register(BroadcastSequenceStep)
class BroadcastSequenceStepAdmin(admin.ModelAdmin):
    list_display = ("sequence", "order", "delay_hours", "sent_count", "read_count")
    list_filter = ("sequence__status",)
    readonly_fields = ("id",)


@admin.register(SequenceEnrollment)
class SequenceEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("sequence", "conversation", "current_step", "status", "next_send_at")
    list_filter = ("status",)
    readonly_fields = ("id", "enrolled_at")


@admin.register(WhatsAppAnalytics)
class WhatsAppAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("social_account", "date", "messages_inbound", "messages_outbound", "ai_replies")
    list_filter = ("date",)
    readonly_fields = ("id",)


@admin.register(WeeklyDigest)
class WeeklyDigestAdmin(admin.ModelAdmin):
    list_display = ("user", "week_start", "week_end", "model_used")
    readonly_fields = ("id", "created_at")


@admin.register(WhatsAppChannel)
class WhatsAppChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "social_account", "status", "follower_count", "auto_curate")
    list_filter = ("status", "auto_curate")
    readonly_fields = ("id", "created_at")


@admin.register(ChannelPost)
class ChannelPostAdmin(admin.ModelAdmin):
    list_display = ("channel", "status", "ai_adapted", "source_platform", "reach", "created_at")
    list_filter = ("status", "ai_adapted")
    readonly_fields = ("id", "created_at")
