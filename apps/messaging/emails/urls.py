from django.urls import path

from apps.messaging.emails import views

app_name = "emails"

# V1: transactional + webhook endpoints only. Marketing UI removed.
urlpatterns = [
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
    path("webhooks/resend/", views.resend_webhook, name="resend_webhook"),
]
