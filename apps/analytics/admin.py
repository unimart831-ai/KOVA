from django.contrib import admin

from apps.analytics.models import (
    Competitor,
    CompetitorAnalysis,
    CompetitorInsight,
    CompetitorScreenshot,
    Conversion,
    ConversionJourney,
    ConversionTouchpoint,
    GrowthSnapshot,
    PageView,
    PerformanceRecycle,
    PostMetric,
    ShopifyStore,
    WebsiteEvent,
)


@admin.register(PostMetric)
class PostMetricAdmin(admin.ModelAdmin):
    list_display = ["post", "impressions", "likes", "comments", "shares", "engagement_rate", "fetched_at"]
    readonly_fields = ["fetched_at"]


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "industry", "threat_level", "handle_count", "last_analyzed_at", "is_active"]
    list_filter = ["threat_level", "is_active"]
    search_fields = ["name", "user__email", "twitter_handle", "instagram_handle"]
    readonly_fields = ["created_at", "updated_at", "last_analyzed_at"]


@admin.register(CompetitorAnalysis)
class CompetitorAnalysisAdmin(admin.ModelAdmin):
    list_display = ["competitor", "user", "analysis_type", "tokens_used", "created_at"]
    list_filter = ["analysis_type"]
    search_fields = ["competitor__name", "user__email"]
    readonly_fields = ["created_at"]


@admin.register(CompetitorInsight)
class CompetitorInsightAdmin(admin.ModelAdmin):
    list_display = ["title", "competitor", "insight_type", "priority", "is_acted_on", "is_dismissed", "created_at"]
    list_filter = ["insight_type", "priority", "is_acted_on", "is_dismissed"]
    search_fields = ["title", "competitor__name", "user__email"]
    readonly_fields = ["created_at"]


@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display = ["user", "conversion_type", "revenue", "product", "post", "utm_campaign", "created_at"]
    list_filter = ["conversion_type"]
    search_fields = ["user__email", "utm_campaign", "event_name"]
    readonly_fields = ["created_at"]


class ConversionTouchpointInline(admin.TabularInline):
    model = ConversionTouchpoint
    extra = 0
    readonly_fields = ["touched_at"]


@admin.register(ConversionJourney)
class ConversionJourneyAdmin(admin.ModelAdmin):
    list_display = ["visitor_id", "user", "is_converted", "touchpoint_count", "total_revenue", "created_at"]
    list_filter = ["is_converted"]
    search_fields = ["visitor_id", "user__email"]
    readonly_fields = ["created_at"]
    inlines = [ConversionTouchpointInline]


@admin.register(ShopifyStore)
class ShopifyStoreAdmin(admin.ModelAdmin):
    list_display = ["shop_domain", "user", "is_active", "orders_tracked", "total_revenue", "last_order_at"]
    list_filter = ["is_active"]
    search_fields = ["shop_domain", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(WebsiteEvent)
class WebsiteEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "user", "page_url", "utm_source", "visitor_id", "revenue", "created_at"]
    list_filter = ["event_type", "device_type"]
    search_fields = ["user__email", "page_url", "visitor_id", "utm_campaign"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["user", "post", "journey"]


@admin.register(ConversionTouchpoint)
class ConversionTouchpointAdmin(admin.ModelAdmin):
    """Individual touchpoint within a conversion journey. Already inlined
    on Journey; this top-level view supports cross-journey debugging."""

    list_display = ["journey", "touch_type", "utm_source", "utm_medium", "utm_campaign", "touched_at"]
    list_filter = ["touch_type", "utm_source", "device_type"]
    search_fields = ["journey__visitor_id", "journey__user__email", "utm_campaign"]
    readonly_fields = ["touched_at"]
    raw_id_fields = ["journey", "post"]
    date_hierarchy = "touched_at"


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    """Raw page-view events. High-volume table — use date_hierarchy + search
    to drill into specific sessions."""

    list_display = ["user", "section", "path_short", "viewed_at"]
    list_filter = ["section", "viewed_at"]
    search_fields = ["user__email", "path"]
    readonly_fields = ["viewed_at"]
    raw_id_fields = ["user"]
    date_hierarchy = "viewed_at"

    def path_short(self, obj):
        p = obj.path or ""
        return (p[:60] + "...") if len(p) > 60 else p
    path_short.short_description = "Path"


@admin.register(GrowthSnapshot)
class GrowthSnapshotAdmin(admin.ModelAdmin):
    """Daily snapshot of follower/engagement counts per platform.
    Powers the growth charts on the analytics dashboard."""

    list_display = [
        "user", "social_account", "snapshot_date",
        "followers", "following", "posts_count",
    ]
    list_filter = ["snapshot_date", "social_account__platform"]
    search_fields = ["user__email"]
    raw_id_fields = ["user", "social_account"]
    date_hierarchy = "snapshot_date"


@admin.register(CompetitorScreenshot)
class CompetitorScreenshotAdmin(admin.ModelAdmin):
    """User-uploaded competitor screenshots, AI-analyzed for counter-strategy."""

    list_display = ["user", "competitor_name", "status", "posts_generated", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["user__email", "competitor_name", "user_notes"]
    raw_id_fields = ["user", "competitor", "counter_seed"]
    readonly_fields = ["created_at", "completed_at"]
    date_hierarchy = "created_at"


@admin.register(PerformanceRecycle)
class PerformanceRecycleAdmin(admin.ModelAdmin):
    """Tracks past winners that the recycle agent re-promoted via email or
    re-post. Audit trail for content recycling."""

    list_display = [
        "user", "source_post", "status",
        "performance_multiplier", "trigger_metric", "detected_at",
    ]
    list_filter = ["status", "trigger_metric", "detected_at"]
    search_fields = ["user__email", "email_subject"]
    raw_id_fields = ["user", "source_post", "post_metric", "email_campaign"]
    readonly_fields = ["detected_at", "sent_at"]
    date_hierarchy = "detected_at"
