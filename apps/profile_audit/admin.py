from django.contrib import admin

from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion


class SuggestionInline(admin.TabularInline):
    model = ProfileUpdateSuggestion
    extra = 0
    fields = ("field_name", "status", "suggested_value", "applied_at", "error_message")
    readonly_fields = ("applied_at",)


@admin.register(ProfileAudit)
class ProfileAuditAdmin(admin.ModelAdmin):
    list_display = (
        "user", "social_account", "completeness_score",
        "missing_count", "thin_count", "audited_at",
    )
    list_filter = ("social_account__platform", "audited_at")
    search_fields = ("user__email", "social_account__username")
    readonly_fields = ("audited_at",)
    raw_id_fields = ("user", "social_account")
    date_hierarchy = "audited_at"
    inlines = [SuggestionInline]

    def missing_count(self, obj):
        return len(obj.fields_missing or [])
    missing_count.short_description = "Missing"

    def thin_count(self, obj):
        return len(obj.fields_thin or [])
    thin_count.short_description = "Thin"


@admin.register(ProfileUpdateSuggestion)
class ProfileUpdateSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "social_account", "field_name", "status",
        "applied_at", "created_at",
    )
    list_filter = ("status", "social_account__platform", "field_name")
    search_fields = ("user__email", "field_name", "suggested_value")
    readonly_fields = ("created_at", "updated_at", "applied_at")
    raw_id_fields = ("audit", "user", "social_account")
    date_hierarchy = "created_at"
