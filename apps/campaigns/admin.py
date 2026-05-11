from django.contrib import admin

from apps.campaigns.models import Campaign, CampaignEmail, CampaignNote, CampaignSeed


class CampaignSeedInline(admin.TabularInline):
    model = CampaignSeed
    extra = 0
    raw_id_fields = ("seed",)


class CampaignEmailInline(admin.TabularInline):
    model = CampaignEmail
    extra = 0
    raw_id_fields = ("email_campaign",)


class CampaignNoteInline(admin.TabularInline):
    model = CampaignNote
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "objective", "status", "start_date", "end_date", "created_at")
    list_filter = ("status", "objective")
    search_fields = ("name", "user__email")
    readonly_fields = ("id", "utm_campaign_tag", "metrics_snapshot", "created_at", "updated_at")
    inlines = [CampaignSeedInline, CampaignEmailInline, CampaignNoteInline]


@admin.register(CampaignSeed)
class CampaignSeedAdmin(admin.ModelAdmin):
    """Link between a Campaign and a ContentSeed. Most management happens
    via the inline on Campaign — this view is for cross-campaign search."""

    list_display = ("campaign", "seed", "role", "sequence_order", "created_at")
    list_filter = ("role",)
    search_fields = ("campaign__name", "seed__idea")
    raw_id_fields = ("campaign", "seed")
    readonly_fields = ("created_at",)


@admin.register(CampaignEmail)
class CampaignEmailAdmin(admin.ModelAdmin):
    """Link between a Campaign and an EmailCampaign."""

    list_display = ("campaign", "email_campaign", "role", "sequence_order", "created_at")
    list_filter = ("role",)
    search_fields = ("campaign__name", "email_campaign__name")
    raw_id_fields = ("campaign", "email_campaign")
    readonly_fields = ("created_at",)


@admin.register(CampaignNote)
class CampaignNoteAdmin(admin.ModelAdmin):
    """Notes attached to campaigns — used for context, debrief, post-mortem."""

    list_display = ("campaign", "user", "note_type", "content_short", "created_at")
    list_filter = ("note_type",)
    search_fields = ("campaign__name", "user__email", "content")
    raw_id_fields = ("campaign", "user")
    readonly_fields = ("created_at",)

    def content_short(self, obj):
        c = obj.content or ""
        return (c[:80] + "...") if len(c) > 80 else c
    content_short.short_description = "Content"
