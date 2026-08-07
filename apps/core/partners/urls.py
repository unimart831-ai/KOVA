from django.urls import path

from . import views

app_name = "partners"

urlpatterns = [
    # Public pages
    path("", views.partners_landing, name="landing"),
    path("apply/", views.partners_apply, name="apply"),
    path("articles/<slug:slug>/", views.partners_article, name="article"),
    path("<slug:slug>/join/", views.marketplace_vendor_join, name="marketplace_join"),
    # Authenticated dashboard
    path("dashboard/", views.partner_dashboard, name="dashboard"),
    path("dashboard/payout/", views.partner_payout_request, name="payout_request"),
    path("assets/", views.partner_assets, name="assets"),
]
