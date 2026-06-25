from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("", views.billing_overview, name="overview"),
    path("pricing/", views.pricing, name="pricing"),
    path("contact-sales/", views.contact_sales, name="contact_sales"),
    # Stripe (kept for future international billing)
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/addon/", views.stripe_addon_checkout, name="stripe_addon_checkout"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("portal/", views.portal, name="portal"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe_webhook"),
    # M-Pesa
    path("mpesa/checkout/", views.mpesa_checkout, name="mpesa_checkout"),
    path("mpesa/addon/checkout/", views.mpesa_addon_checkout, name="mpesa_addon_checkout"),
    path("mpesa/waiting/", views.mpesa_waiting, name="mpesa_waiting"),
    path("mpesa/status/", views.mpesa_check_status, name="mpesa_check_status"),
    path("mpesa/success/", views.mpesa_success, name="mpesa_success"),
    path("webhook/mpesa/", views.mpesa_webhook, name="mpesa_webhook"),
]
