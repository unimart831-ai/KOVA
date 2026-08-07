from django.contrib import admin

from apps.messaging.emails.models import (
    EmailCampaign,
    EmailList,
    EmailLog,
    EmailSequence,
    EmailSequenceStep,
    EmailSubscriber,
    SequenceEnrollment,
)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("to_email", "email_type", "subject", "status", "created_at", "sent_at")
    list_filter = ("email_type", "status", "created_at")
    search_fields = ("to_email", "subject", "user__email")
    readonly_fields = (
        "id", "user", "to_email", "from_email", "email_type", "subject",
        "status", "provider_message_id", "metadata",
        "created_at", "sent_at", "delivered_at", "opened_at", "clicked_at",
        "failed_at", "error_message",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(EmailSubscriber)
class EmailSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "source", "status", "engagement_score", "subscribed_at")
    list_filter = ("status", "source")
    search_fields = ("email", "name")


@admin.register(EmailList)
class EmailListAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "subscriber_count", "is_smart", "created_at")
    list_filter = ("is_smart",)
    search_fields = ("name",)


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "status", "total_sent", "total_opened", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "subject")


class EmailSequenceStepInline(admin.TabularInline):
    model = EmailSequenceStep
    extra = 1
    ordering = ("step_number",)


@admin.register(EmailSequence)
class EmailSequenceAdmin(admin.ModelAdmin):
    list_display = ("name", "trigger_type", "is_active", "created_at")
    list_filter = ("trigger_type", "is_active")
    inlines = [EmailSequenceStepInline]


@admin.register(SequenceEnrollment)
class SequenceEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("subscriber", "sequence", "current_step", "status", "enrolled_at")
    list_filter = ("status",)


@admin.register(EmailSequenceStep)
class EmailSequenceStepAdmin(admin.ModelAdmin):
    """Individual step in an EmailSequence. Usually managed via inline on
    the parent sequence — this view supports cross-sequence search and
    fixing a single broken step."""

    list_display = ("sequence", "step_number", "subject", "delay_days", "delay_hours", "ai_generated")
    list_filter = ("ai_generated",)
    search_fields = ("sequence__name", "subject")
    raw_id_fields = ("sequence",)
