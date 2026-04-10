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
