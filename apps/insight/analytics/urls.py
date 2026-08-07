from django.urls import path

from apps.insight.analytics import views, webhooks
from apps.insight.analytics.pixel import pixel_settings, pixel_track, pixel_regenerate_token, pixel_events, pixel_test

app_name = "analytics"

urlpatterns = [
    path("", views.insights, name="insights"),
    path("insights/<uuid:pk>/action/", views.insight_action, name="insight_action"),
    # Revenue Attribution
    path("revenue/", views.revenue_dashboard, name="revenue"),
    path("revenue/campaign/<uuid:campaign_id>/", views.campaign_revenue_detail, name="campaign_revenue"),
    path("revenue/export/assets/", views.export_asset_breakdown_csv, name="export_asset_breakdown"),
    path("revenue/shopify/connect/", views.shopify_connect, name="shopify_connect"),
    path("revenue/shopify/oauth/begin/", views.shopify_oauth_begin, name="shopify_oauth_begin"),
    path("revenue/shopify/oauth/callback/", views.shopify_oauth_callback, name="shopify_oauth_callback"),
    path("revenue/shopify/<uuid:pk>/disconnect/", views.shopify_disconnect, name="shopify_disconnect"),
    path("revenue/shopify/<uuid:pk>/sync-products/", views.shopify_sync_products, name="shopify_sync_products"),
    # Attribution Dashboard
    path("attribution/", views.attribution_dashboard, name="attribution"),
    path("attribution/download/", views.download_report, name="download_report"),
    # Content Intelligence
    path("intelligence/", views.content_intelligence, name="content_intelligence"),
    # Kova Pixel
    path("pixel/", pixel_settings, name="pixel_settings"),
    path("pixel/track/", pixel_track, name="pixel_track"),
    path("pixel/regenerate/", pixel_regenerate_token, name="pixel_regenerate"),
    path("pixel/events/", pixel_events, name="pixel_events"),
    path("pixel/test/", pixel_test, name="pixel_test"),
    path("pixel/kova-pixel.js", views.serve_pixel_js, name="pixel_js"),
    # Performance recycle
    path("recycle/", views.performance_recycle, name="performance_recycle"),
    path("recycle/<uuid:pk>/action/", views.recycle_action, name="recycle_action"),
    # Webhooks (external — no auth)
    path("webhooks/shopify/order/", webhooks.shopify_order_webhook, name="shopify_order_webhook"),
    path("webhooks/shopify/products/", webhooks.shopify_product_webhook, name="shopify_product_webhook"),
    path("webhooks/mpesa/commerce/", webhooks.mpesa_commerce_callback, name="mpesa_commerce_callback"),
]
