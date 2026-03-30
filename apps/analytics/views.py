from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum
from django.shortcuts import render

from apps.analytics.models import PostMetric


@login_required
def insights(request):
    """Analytics dashboard with real metrics."""
    metrics = PostMetric.objects.filter(
        post__user=request.user,
        post__status="published",
    ).select_related("post__social_account")

    # Platform filter
    platform = request.GET.get("platform")
    if platform:
        metrics = metrics.filter(post__social_account__platform=platform)

    totals = metrics.aggregate(
        total_impressions=Sum("impressions"),
        total_reach=Sum("reach"),
        total_likes=Sum("likes"),
        total_comments=Sum("comments"),
        total_shares=Sum("shares"),
        total_saves=Sum("saves"),
        total_clicks=Sum("clicks"),
        avg_engagement=Avg("engagement_rate"),
    )

    top_posts = metrics.order_by("-engagement_rate")[:5]

    published_count = request.user.posts.filter(status="published")
    if platform:
        published_count = published_count.filter(social_account__platform=platform)
    published_count = published_count.count()

    # Connected platforms for filter dropdown
    connected_platforms = list(
        request.user.social_accounts.filter(is_active=True)
        .values_list("platform", flat=True)
        .distinct()
    )

    return render(request, "analytics/insights.html", {
        "page_title": "Insights & Analytics",
        "totals": totals,
        "top_posts": top_posts,
        "published_count": published_count,
        "has_data": metrics.exists(),
        "connected_platforms": connected_platforms,
        "current_platform": platform,
    })
