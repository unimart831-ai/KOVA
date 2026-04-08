from django.contrib import admin

from apps.leads.models import Lead, LeadActivity


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
