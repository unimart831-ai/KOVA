from django.urls import path

from apps.whatsapp import views, webhook

app_name = "whatsapp"

urlpatterns = [
    # Webhook (Meta sends events here — GET for verification, POST for events)
    path("webhook/", webhook.whatsapp_webhook, name="webhook"),
    # Inbox views
    path("", views.whatsapp_inbox, name="inbox"),
    path("conversation/<uuid:pk>/", views.whatsapp_conversation, name="conversation"),
    path("conversation/<uuid:pk>/send/", views.send_message, name="send_message"),
    path("conversation/<uuid:pk>/toggle-ai/", views.toggle_ai, name="toggle_ai"),
    # Templates
    path("templates/", views.template_list, name="template_list"),
    path("templates/create/", views.template_create, name="template_create"),
]
