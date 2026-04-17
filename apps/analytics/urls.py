from django.urls import path

from apps.analytics import views, webhooks
from apps.analytics.pixel import pixel_settings, pixel_track, pixel_regenerate_token, pixel_events, pixel_test

app_name = "analytics"

urlpatterns = [
    path("", views.insights, name="insights"),
    # Competitor Intelligence
    path("competitors/", views.competitor_dashboard, name="competitors"),
    path("competitors/add/", views.competitor_add, name="competitor_add"),
    path("competitors/landscape/", views.competitor_landscape, name="competitor_landscape"),
    path("competitors/<uuid:pk>/", views.competitor_detail, name="competitor_detail"),
    path("competitors/<uuid:pk>/edit/", views.competitor_edit, name="competitor_edit"),
    path("competitors/<uuid:pk>/analyze/", views.competitor_analyze, name="competitor_analyze"),
    path("competitors/<uuid:pk>/delete/", views.competitor_delete, name="competitor_delete"),
    path("insights/<uuid:pk>/action/", views.insight_action, name="insight_action"),
    # Revenue Attribution
    path("revenue/", views.revenue_dashboard, name="revenue"),
    path("revenue/shopify/connect/", views.shopify_connect, name="shopify_connect"),
    path("revenue/shopify/<uuid:pk>/disconnect/", views.shopify_disconnect, name="shopify_disconnect"),
    # Attribution Dashboard (the single answer)
    path("attribution/", views.attribution_dashboard, name="attribution"),
    # Kova Pixel (Sprint T2A)
    path("pixel/", pixel_settings, name="pixel_settings"),
    path("pixel/track/", pixel_track, name="pixel_track"),
    path("pixel/regenerate/", pixel_regenerate_token, name="pixel_regenerate"),
    path("pixel/events/", pixel_events, name="pixel_events"),
    path("pixel/test/", pixel_test, name="pixel_test"),
    path("pixel/kova-pixel.js", views.serve_pixel_js, name="pixel_js"),
    # Webhooks (external — no auth)
    path("webhooks/shopify/order/", webhooks.shopify_order_webhook, name="shopify_order_webhook"),
    path("webhooks/mpesa/commerce/", webhooks.mpesa_commerce_callback, name="mpesa_commerce_callback"),
]
