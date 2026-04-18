"""
Marketplace Partner API URL routing.

All endpoints prefixed with /api/v1/partner/
Authenticated via X-Kova-Partner-Key header.
"""

from django.urls import path

from . import partner_views

app_name = "partner_api"

urlpatterns = [
    # Marketplace info
    path("info/", partner_views.MarketplaceInfoView.as_view(), name="info"),

    # Seller management
    path("sellers/", partner_views.SellerListCreateView.as_view(), name="seller-list-create"),
    path("sellers/<str:external_seller_id>/", partner_views.SellerDetailView.as_view(), name="seller-detail"),
    path("sellers/<str:external_seller_id>/suspend/", partner_views.SellerSuspendView.as_view(), name="seller-suspend"),
    path("sellers/<str:external_seller_id>/activate/", partner_views.SellerActivateView.as_view(), name="seller-activate"),

    # Product sync
    path("sellers/<str:external_seller_id>/products/sync/", partner_views.ProductSyncView.as_view(), name="product-sync"),

    # Stats
    path("stats/", partner_views.MarketplaceStatsView.as_view(), name="stats"),
]
