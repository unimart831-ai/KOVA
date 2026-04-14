from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response

from apps.agents.models import AgentAction, AgentConfig
from apps.content.models import ContentSeed, Post
from apps.platforms.models import SocialAccount

from .serializers import (
    AgentActionSerializer,
    AgentConfigSerializer,
    ContentSeedSerializer,
    ConversionSerializer,
    PostMetricSerializer,
    PostSerializer,
    SocialAccountSerializer,
)


# ─── Plan-based API access permission ────────────────────────────────────────

class HasAPIAccess(BasePermission):
    """Only allow Pro and Agency plan users to access the API."""
    message = "API access requires a Pro or Agency plan."

    def has_permission(self, request, view):
        from apps.billing.enforcement import check_api_access
        allowed, msg = check_api_access(request.user)
        if not allowed:
            self.message = msg
        return allowed


# ─── Platforms ───────────────────────────────────────────────────────────────

class SocialAccountListView(generics.ListAPIView):
    """List connected social accounts."""
    serializer_class = SocialAccountSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user, is_active=True)


# ─── Content Seeds ───────────────────────────────────────────────────────────

class SeedListCreateView(generics.ListCreateAPIView):
    """List or create content seeds."""
    serializer_class = ContentSeedSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return ContentSeed.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        from apps.billing.enforcement import check_seed_limit
        allowed, msg = check_seed_limit(self.request.user)
        if not allowed:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(msg)
        serializer.save(user=self.request.user)


class SeedDetailView(generics.RetrieveAPIView):
    """Retrieve a content seed."""
    serializer_class = ContentSeedSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return ContentSeed.objects.filter(user=self.request.user)


# ─── Posts ───────────────────────────────────────────────────────────────────

class PostListView(generics.ListAPIView):
    """List user's posts with optional status filter."""
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        qs = Post.objects.filter(user=self.request.user).select_related(
            "social_account"
        ).order_by("-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        platform = self.request.query_params.get("platform")
        if platform:
            qs = qs.filter(social_account__platform=platform)

        return qs[:100]


class PostDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update (edit text, reschedule) a post."""
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return Post.objects.filter(user=self.request.user).select_related(
            "social_account"
        )


# ─── Analytics ───────────────────────────────────────────────────────────────

class PostMetricsView(generics.RetrieveAPIView):
    """Get metrics for a specific post."""
    serializer_class = PostMetricSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        from apps.analytics.models import PostMetric
        return PostMetric.objects.filter(post__user=self.request.user).select_related("post")


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasAPIAccess])
def analytics_summary(request):
    """Quick aggregate analytics for the authenticated user."""
    from django.db.models import Avg, Sum

    from apps.analytics.models import PostMetric

    posts = Post.objects.filter(user=request.user)
    metrics = PostMetric.objects.filter(post__user=request.user)

    agg = metrics.aggregate(
        total_impressions=Sum("impressions"),
        total_likes=Sum("likes"),
        total_comments=Sum("comments"),
        total_shares=Sum("shares"),
        avg_engagement_rate=Avg("engagement_rate"),
    )

    return Response({
        "total_posts": posts.count(),
        "published_posts": posts.filter(status="published").count(),
        "scheduled_posts": posts.filter(status="scheduled").count(),
        **{k: v or 0 for k, v in agg.items()},
    })


# ─── Agents ──────────────────────────────────────────────────────────────────

class AgentConfigListView(generics.ListAPIView):
    """List agent configurations."""
    serializer_class = AgentConfigSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return AgentConfig.objects.filter(user=self.request.user)


class AgentActionListView(generics.ListAPIView):
    """List recent agent actions."""
    serializer_class = AgentActionSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        qs = AgentAction.objects.filter(user=self.request.user).order_by("-created_at")
        agent_type = self.request.query_params.get("agent_type")
        if agent_type:
            qs = qs.filter(agent_type=agent_type)
        return qs[:50]


# ─── Conversions / Revenue Attribution ────────────────────────────────────────

class ConversionListCreateView(generics.ListCreateAPIView):
    """List or create conversion events (revenue attribution)."""
    serializer_class = ConversionSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        from apps.analytics.models import Conversion
        qs = Conversion.objects.filter(user=self.request.user).order_by("-created_at")
        ctype = self.request.query_params.get("type")
        if ctype:
            qs = qs.filter(conversion_type=ctype)
        return qs[:100]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
