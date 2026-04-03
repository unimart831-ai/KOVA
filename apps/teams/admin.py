from django.contrib import admin

from .models import Team, TeamInvitation, TeamMember


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    readonly_fields = ("joined_at",)


class TeamInvitationInline(admin.TabularInline):
    model = TeamInvitation
    extra = 0
    readonly_fields = ("token", "created_at")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "member_count", "created_at")
    search_fields = ("name", "slug", "owner__email")
    readonly_fields = ("id", "created_at")
    inlines = [TeamMemberInline, TeamInvitationInline]

    def member_count(self, obj):
        return obj.members.count()

    member_count.short_description = "Members"


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "team", "role", "accepted", "is_expired", "created_at")
    list_filter = ("accepted", "role")
    search_fields = ("email", "team__name")
    readonly_fields = ("token",)
