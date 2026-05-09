from django.contrib import admin

from apps.calendar_intel.models import (
    CustomEvent,
    Holiday,
    HolidayDraft,
    HolidayOccurrence,
    UserHolidayPreference,
)


class HolidayOccurrenceInline(admin.TabularInline):
    model = HolidayOccurrence
    extra = 0
    fields = ("year", "date", "notes")
    readonly_fields = ()
    ordering = ("year",)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "date_type",
        "countries_display",
        "religion",
        "sensitivity_level",
        "default_relevance_score",
        "is_active",
        "source",
    )
    list_filter = (
        "category",
        "religion",
        "sensitivity_level",
        "is_active",
        "requires_opt_in",
        "source",
    )
    search_fields = ("name", "slug", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [HolidayOccurrenceInline]
    fieldsets = (
        ("Identity", {
            "fields": ("name", "slug", "short_description", "is_active", "source", "notes"),
        }),
        ("Date computation", {
            "fields": ("date_type", "date_config"),
            "description": "See date_engine.py for date_config schemas per date_type.",
        }),
        ("Geographic scope", {
            "fields": ("countries", "excluded_countries"),
            "description": "Empty countries = global. ISO 3166-1 alpha-2 codes.",
        }),
        ("Categorization & sensitivity", {
            "fields": ("category", "religion", "industries", "sensitivity_level", "requires_opt_in"),
        }),
        ("Defaults for relevance scoring", {
            "fields": ("default_relevance_score", "suggested_post_count", "lead_time_days"),
        }),
        ("Content guidance", {
            "fields": ("tone_hint", "angles", "avoid_phrases"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def countries_display(self, obj):
        if not obj.countries:
            return "🌍 Global"
        return ", ".join(obj.countries[:5]) + ("…" if len(obj.countries) > 5 else "")
    countries_display.short_description = "Countries"


@admin.register(HolidayOccurrence)
class HolidayOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("holiday", "year", "date", "notes")
    list_filter = ("year", "holiday__category", "holiday__religion")
    search_fields = ("holiday__name", "holiday__slug")
    date_hierarchy = "date"
    ordering = ("-date",)
    autocomplete_fields = ("holiday",)


@admin.register(UserHolidayPreference)
class UserHolidayPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "holiday",
        "is_enabled",
        "auto_draft_posts",
        "muted_until",
        "updated_at",
    )
    list_filter = ("is_enabled", "auto_draft_posts", "holiday__category")
    search_fields = ("user__email", "holiday__name", "holiday__slug")
    autocomplete_fields = ("user", "holiday")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomEvent)
class CustomEventAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "date", "recurrence", "is_active", "auto_draft_posts")
    list_filter = ("recurrence", "is_active", "auto_draft_posts")
    search_fields = ("name", "user__email", "description")
    autocomplete_fields = ("user",)
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")


@admin.register(HolidayDraft)
class HolidayDraftAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "moment_name",
        "target_date",
        "status",
        "relevance_score",
        "created_at",
    )
    list_filter = ("status", "target_date")
    search_fields = (
        "user__email",
        "holiday_occurrence__holiday__name",
        "custom_event__name",
    )
    autocomplete_fields = ("user", "holiday_occurrence", "custom_event")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "target_date"

    def moment_name(self, obj):
        return obj.moment_name
    moment_name.short_description = "Moment"
