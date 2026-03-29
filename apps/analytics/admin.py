from django.contrib import admin

from apps.analytics.models import PostMetric


@admin.register(PostMetric)
class PostMetricAdmin(admin.ModelAdmin):
    list_display = ["post", "impressions", "likes", "comments", "shares", "engagement_rate", "fetched_at"]
    readonly_fields = ["fetched_at"]
