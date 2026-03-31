from django.contrib import admin

from apps.analytics.models import (
    Competitor,
    CompetitorAnalysis,
    CompetitorInsight,
    PostMetric,
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
