from django.contrib import admin

from .models import (
    KenyanEvent,
    MemeAdaptation,
    MemePreferences,
    TrendAlert,
    TrendingMeme,
)


@admin.register(TrendingMeme)
class TrendingMemeAdmin(admin.ModelAdmin):
    list_display = [
        "title", "category", "lifecycle", "virality_score",
        "brand_safety_score", "cultural_relevance_score", "adaptation_count", "detected_at",
    ]
    list_filter = ["lifecycle", "category", "humor_type", "source_platform"]
    search_fields = ["title", "description", "tags"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(MemeAdaptation)
class MemeAdaptationAdmin(admin.ModelAdmin):
    list_display = [
        "trending_meme", "user", "status", "brand_relevance_score",
        "humor_preserved_score", "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["adapted_text", "user__email", "trending_meme__title"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["user", "trending_meme", "post"]


@admin.register(KenyanEvent)
class KenyanEventAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "event_type", "meme_potential", "sensitivity", "annual"]
    list_filter = ["event_type", "meme_potential", "sensitivity", "annual"]
    search_fields = ["name", "description"]
    readonly_fields = ["id"]


@admin.register(MemePreferences)
class MemePreferencesAdmin(admin.ModelAdmin):
    list_display = ["user", "is_active", "risk_tolerance", "max_memes_per_week", "auto_queue"]
    list_filter = ["is_active", "risk_tolerance"]
    raw_id_fields = ["user"]


@admin.register(TrendAlert)
class TrendAlertAdmin(admin.ModelAdmin):
    """15-minute trend response system: auto-detected trends + one-tap
    brand-safe content generation. Admin used for cross-user trend audits
    and debugging expiry/generation issues."""

    list_display = [
        "trend_topic_short", "user", "trend_source", "status",
        "trend_score", "urgency_hours", "posts_generated", "detected_at",
    ]
    list_filter = ["status", "trend_source"]
    search_fields = ["trend_topic", "trend_context", "brand_angle", "user__email"]
    readonly_fields = ["detected_at", "approved_at"]
    raw_id_fields = ["user", "trending_meme", "kenyan_event", "content_seed"]
    date_hierarchy = "detected_at"

    def trend_topic_short(self, obj):
        t = obj.trend_topic or ""
        return (t[:60] + "...") if len(t) > 60 else t
    trend_topic_short.short_description = "Trend topic"
