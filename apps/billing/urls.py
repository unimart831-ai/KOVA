from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("", views.billing_overview, name="overview"),
    path("pricing/", views.pricing, name="pricing"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("portal/", views.portal, name="portal"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
