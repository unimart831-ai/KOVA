from django.contrib import admin

from .models import Brand, Team, TeamActivity, TeamInvitation, TeamMember


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    readonly_fields = ("joined_at",)


class TeamInvitationInline(admin.TabularInline):
    model = TeamInvitation
    extra = 0
    readonly_fields = ("token", "created_at")


class BrandInline(admin.TabularInline):
    model = Brand
    extra = 0
    readonly_fields = ("id", "created_at")
    fields = ("name", "slug", "industry", "is_active", "created_at")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "member_count", "brand_count", "created_at")
    search_fields = ("name", "slug", "owner__email")
    readonly_fields = ("id", "created_at")
    inlines = [TeamMemberInline, BrandInline, TeamInvitationInline]

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "Members"

    def brand_count(self, obj):
        return obj.brands.count()
    brand_count.short_description = "Brands"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "industry", "is_active", "created_at")
    list_filter = ("is_active", "industry")
    search_fields = ("name", "team__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TeamActivity)
class TeamActivityAdmin(admin.ModelAdmin):
    list_display = ("team", "actor", "event_type", "description", "created_at")
    list_filter = ("event_type",)
    search_fields = ("team__name", "description")
    readonly_fields = ("id", "team", "actor", "event_type", "description", "metadata", "created_at")
