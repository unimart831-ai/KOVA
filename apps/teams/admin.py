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


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    """Direct top-level view of team membership. Inline on Team covers
    most cases but this is useful when searching by user across all teams."""

    list_display = ("user", "team", "role", "invited_by", "joined_at")
    list_filter = ("role",)
    search_fields = ("user__email", "team__name", "invited_by__email")
    raw_id_fields = ("team", "user", "invited_by")
    readonly_fields = ("joined_at",)


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    """Pending and historical team invitations. Look here when a user
    reports an invitation email didn't arrive or expired."""

    list_display = ("email", "team", "role", "accepted", "invited_by", "created_at", "expires_at")
    list_filter = ("accepted", "role")
    search_fields = ("email", "team__name", "invited_by__email")
    raw_id_fields = ("team", "invited_by")
    readonly_fields = ("token", "created_at")
    date_hierarchy = "created_at"
