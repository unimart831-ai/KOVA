from django.urls import path

from apps.emails import views

app_name = "emails"

urlpatterns = [
    # Resend delivery webhooks
    path("webhooks/resend/", views.resend_webhook, name="resend_webhook"),
]
