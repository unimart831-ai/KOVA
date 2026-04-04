from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Platforms
    path("platforms/", views.SocialAccountListView.as_view(), name="platforms"),

    # Seeds
    path("seeds/", views.SeedListCreateView.as_view(), name="seed-list"),
    path("seeds/<uuid:pk>/", views.SeedDetailView.as_view(), name="seed-detail"),

    # Posts
    path("posts/", views.PostListView.as_view(), name="post-list"),
    path("posts/<uuid:pk>/", views.PostDetailView.as_view(), name="post-detail"),

    # Analytics
    path("analytics/summary/", views.analytics_summary, name="analytics-summary"),
    path("analytics/metrics/<uuid:pk>/", views.PostMetricsView.as_view(), name="post-metrics"),

    # Agents
    path("agents/", views.AgentConfigListView.as_view(), name="agent-list"),
    path("agents/actions/", views.AgentActionListView.as_view(), name="agent-actions"),

    # Conversions / Revenue Attribution
    path("conversions/", views.ConversionListCreateView.as_view(), name="conversion-list"),
]
