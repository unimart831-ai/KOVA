from django.contrib import admin

from apps.leads.models import (
    Lead,
    LeadActivity,
    LeadEnrollment,
    NurtureSequence,
    NurtureStep,
)


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ("activity_type", "description", "created_at")
    ordering = ("-created_at",)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "status", "priority", "source_type", "first_seen_at")
    list_filter = ("status", "priority", "source_type")
    search_fields = ("email", "name", "phone")
    readonly_fields = ("first_seen_at", "last_activity_at")
    inlines = [LeadActivityInline]


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("lead", "activity_type", "created_at")
    list_filter = ("activity_type",)
    readonly_fields = ("created_at",)


class NurtureStepInline(admin.TabularInline):
    model = NurtureStep
    extra = 0
    fields = ("order", "delay_hours", "action_type", "email_subject", "tag_value")
    ordering = ("order",)


@admin.register(NurtureSequence)
class NurtureSequenceAdmin(admin.ModelAdmin):
    """User-defined sequences that auto-engage leads (email tags, status changes)
    after they trigger an entry condition."""

    list_display = ("name", "user", "trigger", "trigger_platform", "is_active", "step_count", "created_at")
    list_filter = ("is_active", "trigger", "trigger_platform")
    search_fields = ("name", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)
    inlines = [NurtureStepInline]
    date_hierarchy = "created_at"

    def step_count(self, obj):
        return obj.steps.count()
    step_count.short_description = "Steps"


@admin.register(NurtureStep)
class NurtureStepAdmin(admin.ModelAdmin):
    """Individual step in a NurtureSequence. Usually managed via the inline
    on the sequence — this view is for cross-sequence searches."""

    list_display = ("sequence", "order", "action_type", "delay_hours", "email_subject")
    list_filter = ("action_type",)
    search_fields = ("sequence__name", "email_subject")
    raw_id_fields = ("sequence",)


@admin.register(LeadEnrollment)
class LeadEnrollmentAdmin(admin.ModelAdmin):
    """Tracks which leads are currently progressing through which sequence.
    Supports debugging when a lead doesn't receive the next step."""

    list_display = (
        "lead", "sequence", "current_step",
        "completed", "paused", "next_step_at", "enrolled_at",
    )
    list_filter = ("completed", "paused")
    search_fields = ("lead__email", "sequence__name")
    raw_id_fields = ("lead", "sequence")
    readonly_fields = ("enrolled_at",)
    date_hierarchy = "enrolled_at"
