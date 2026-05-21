from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
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
    ProductCategorySerializer,
    ProductSerializer,
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

@extend_schema(tags=["Platforms"])
class SocialAccountListView(generics.ListAPIView):
    """List connected social accounts."""
    serializer_class = SocialAccountSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "-created_at"

    def get_queryset(self):
        return SocialAccount.objects.filter(user=self.request.user, is_active=True).order_by("-created_at")


# ─── Content Seeds ───────────────────────────────────────────────────────────

@extend_schema(tags=["Seeds"])
class SeedListCreateView(generics.ListCreateAPIView):
    """List or create content seeds."""
    serializer_class = ContentSeedSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "-created_at"

    def get_queryset(self):
        return ContentSeed.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        from apps.billing.enforcement import check_seed_limit
        allowed, msg = check_seed_limit(self.request.user)
        if not allowed:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(msg)
        serializer.save(user=self.request.user)


@extend_schema(tags=["Seeds"])
class SeedDetailView(generics.RetrieveAPIView):
    """Retrieve a content seed."""
    serializer_class = ContentSeedSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return ContentSeed.objects.filter(user=self.request.user)


# ─── Posts ───────────────────────────────────────────────────────────────────

@extend_schema_view(
    get=extend_schema(
        tags=["Posts"],
        parameters=[
            OpenApiParameter("status", str, description="Filter by post status (draft, published, scheduled, etc.)"),
            OpenApiParameter("platform", str, description="Filter by platform (instagram, twitter, etc.)"),
        ],
    ),
)
class PostListView(generics.ListAPIView):
    """List user's posts with optional status and platform filters."""
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "-created_at"

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

        return qs


@extend_schema(tags=["Posts"])
class PostDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update (edit text, reschedule) a post."""
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return Post.objects.filter(user=self.request.user).select_related(
            "social_account"
        )


# ─── Analytics ───────────────────────────────────────────────────────────────

@extend_schema(tags=["Analytics"])
class PostMetricsView(generics.RetrieveAPIView):
    """Get metrics for a specific post."""
    serializer_class = PostMetricSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        from apps.analytics.models import PostMetric
        return PostMetric.objects.filter(post__user=self.request.user).select_related("post")


@extend_schema(tags=["Analytics"])
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

@extend_schema(tags=["Agents"])
class AgentConfigListView(generics.ListAPIView):
    """List agent configurations."""
    serializer_class = AgentConfigSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        return AgentConfig.objects.filter(user=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["Agents"],
        parameters=[
            OpenApiParameter("agent_type", str, description="Filter by agent type (research, create, adapt, etc.)"),
        ],
    ),
)
class AgentActionListView(generics.ListAPIView):
    """List recent agent actions."""
    serializer_class = AgentActionSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "-created_at"

    def get_queryset(self):
        qs = AgentAction.objects.filter(user=self.request.user).order_by("-created_at")
        agent_type = self.request.query_params.get("agent_type")
        if agent_type:
            qs = qs.filter(agent_type=agent_type)
        return qs


# ─── Conversions / Revenue Attribution ────────────────────────────────────────

@extend_schema(tags=["Conversions"])
class ConversionListCreateView(generics.ListCreateAPIView):
    """List or create conversion events (revenue attribution)."""
    serializer_class = ConversionSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "-created_at"

    def get_queryset(self):
        from apps.analytics.models import Conversion
        qs = Conversion.objects.filter(user=self.request.user).order_by("-created_at")
        ctype = self.request.query_params.get("type")
        if ctype:
            qs = qs.filter(conversion_type=ctype)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─── Products / Catalog ──────────────────────────────────────────────────────

@extend_schema(tags=["Products"])
class ProductListCreateView(generics.ListCreateAPIView):
    """
    List or create products in the user's catalog.

    GET params:
      - status: filter by stock_status (in_stock, low_stock, out_of_stock, etc.)
      - category: filter by category UUID
      - featured: filter featured only (any truthy value)
      - offering_type: filter by product/service/digital
      - q: search name/description

    POST: Create a product. Respects plan limits.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "-created_at"

    def get_queryset(self):
        from apps.products.models import Product
        qs = Product.objects.filter(
            user=self.request.user, is_active=True
        ).select_related("category").order_by("-is_featured", "-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(stock_status=status_filter)

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)

        featured = self.request.query_params.get("featured")
        if featured:
            qs = qs.filter(is_featured=True)

        offering_type = self.request.query_params.get("offering_type")
        if offering_type:
            qs = qs.filter(offering_type=offering_type)

        q = self.request.query_params.get("q", "").strip()
        if q:
            from apps.utils.search import full_text_search
            qs = full_text_search(qs, q, ["name", "description"], {"name": "A", "description": "B"})

        return qs

    def perform_create(self, serializer):
        from apps.billing.models import get_plan_limits
        from apps.products.models import Product
        from rest_framework.exceptions import PermissionDenied

        limits = get_plan_limits(self.request.user.profile.plan)
        max_products = limits.get("max_products", 5)
        current = Product.objects.filter(user=self.request.user, is_active=True).count()
        if current >= max_products:
            raise PermissionDenied(
                f"Plan limit reached ({max_products} products). Upgrade to add more."
            )
        product = serializer.save(user=self.request.user)
        product.check_low_stock()
        product.save(update_fields=["stock_status"])


@extend_schema(tags=["Products"])
class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or soft-delete a product.
    DELETE performs soft-delete (sets is_active=False).
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get_queryset(self):
        from apps.products.models import Product
        return Product.objects.filter(user=self.request.user, is_active=True).select_related("category")

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


@extend_schema(tags=["Products"])
class ProductBulkImportView(generics.CreateAPIView):
    """
    Bulk import products via API.

    POST body: {"products": [{"name": "...", "price": 5000, ...}, ...]}
    Each item follows the same fields as ProductSerializer.
    Returns: {"imported": N, "errors": [...]}
    """
    permission_classes = [IsAuthenticated, HasAPIAccess]

    def create(self, request, *args, **kwargs):
        from apps.billing.models import get_plan_limits
        from apps.products.models import Product

        products_data = request.data.get("products", [])
        if not isinstance(products_data, list) or not products_data:
            return Response(
                {"error": "Provide a 'products' array."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limits = get_plan_limits(request.user.profile.plan)
        max_products = limits.get("max_products", 5)
        current = Product.objects.filter(user=request.user, is_active=True).count()
        remaining = max_products - current

        imported = 0
        errors = []

        for i, item in enumerate(products_data):
            if imported >= remaining:
                errors.append({"index": i, "error": "Plan limit reached"})
                break
            serializer = ProductSerializer(data=item, context={"request": request})
            if serializer.is_valid():
                product = serializer.save(user=request.user)
                product.check_low_stock()
                product.save(update_fields=["stock_status"])
                imported += 1
            else:
                errors.append({"index": i, "error": serializer.errors})

        return Response(
            {"imported": imported, "errors": errors},
            status=status.HTTP_201_CREATED if imported else status.HTTP_400_BAD_REQUEST,
        )


@extend_schema(tags=["Products"])
class ProductCategoryListCreateView(generics.ListCreateAPIView):
    """List or create product categories."""
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated, HasAPIAccess]
    ordering = "position"

    def get_queryset(self):
        from apps.products.models import ProductCategory
        return ProductCategory.objects.filter(
            user=self.request.user, is_active=True
        ).order_by("position", "name")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
