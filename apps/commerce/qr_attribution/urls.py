from django.urls import path

from apps.commerce.qr_attribution import views

app_name = "qr_attribution"

urlpatterns = [
    # User-side QR management (login required)
    path("qr/", views.qr_list, name="list"),
    path("qr/new/", views.qr_create, name="create"),
    path("qr/<uuid:pk>/", views.qr_detail, name="detail"),
    path("qr/<uuid:pk>/edit/", views.qr_edit, name="edit"),
    path("qr/<uuid:pk>/delete/", views.qr_delete, name="delete"),
    path("qr/<uuid:pk>/print/", views.qr_print_pdf, name="print"),
    # User-side cashier link helper
    path("walkin/", views.cashier_link, name="cashier_link"),
    # Public cashier UI (per-user slug)
    path("walkin/<slug:slug>/", views.cashier_view, name="cashier_view"),
    path("walkin/<slug:slug>/record/", views.cashier_record, name="cashier_record"),
    # Public scan landing
    path("qr/<slug:token>/", views.scan_landing, name="scan_landing"),
    path("qr/<slug:token>/capture/", views.scan_capture_lead, name="scan_capture"),
]
