from django.urls import path

from apps.analytics import views

app_name = "analytics"

urlpatterns = [
    path("", views.insights, name="insights"),
    # Competitor Intelligence
    path("competitors/", views.competitor_dashboard, name="competitors"),
    path("competitors/add/", views.competitor_add, name="competitor_add"),
    path("competitors/landscape/", views.competitor_landscape, name="competitor_landscape"),
    path("competitors/<uuid:pk>/", views.competitor_detail, name="competitor_detail"),
    path("competitors/<uuid:pk>/analyze/", views.competitor_analyze, name="competitor_analyze"),
    path("competitors/<uuid:pk>/delete/", views.competitor_delete, name="competitor_delete"),
    path("insights/<uuid:pk>/action/", views.insight_action, name="insight_action"),
    # Revenue Attribution
    path("revenue/", views.revenue_dashboard, name="revenue"),
]
