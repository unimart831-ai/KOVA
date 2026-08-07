from django.urls import path

from apps.messaging.whatsapp import views, webhook

app_name = "whatsapp"

urlpatterns = [
    # Webhook (Meta sends events here — GET for verification, POST for events)
    path("webhook/", webhook.whatsapp_webhook, name="webhook"),

    # ── Inbox (Sprint 5A) ────────────────────────────────────────────────
    path("", views.whatsapp_inbox, name="inbox"),
    path("conversation/<uuid:pk>/", views.whatsapp_conversation, name="conversation"),
    path("conversation/<uuid:pk>/save-lead/", views.save_as_lead, name="save_as_lead"),
    path("conversation/<uuid:pk>/send/", views.send_message, name="send_message"),
    path("conversation/<uuid:pk>/toggle-ai/", views.toggle_ai, name="toggle_ai"),

    # ── Templates (Sprint 5A) ────────────────────────────────────────────
    path("templates/", views.template_list, name="template_list"),
    path("templates/create/", views.template_create, name="template_create"),
    path("templates/sync/", views.template_sync, name="template_sync"),
    path("templates/<uuid:pk>/submit/", views.template_submit, name="template_submit"),

    # ── Status Content Studio (Sprint 5C) ────────────────────────────────
    path("status/", views.status_studio, name="status_studio"),
    path("status/create/", views.status_create, name="status_create"),
    path("status/<uuid:pk>/share/", views.status_share, name="status_share"),
    path("status/<uuid:pk>/skip/", views.status_skip, name="status_skip"),
    path("status/repurpose/<uuid:post_id>/", views.status_repurpose, name="status_repurpose"),
    path("status/calendar/", views.status_calendar, name="status_calendar"),

    # V1: broadcasts / sequences / channels UI removed (models kept).
    # ── Analytics (lightweight) ──────────────────────────────────────────
    path("analytics/", views.wa_analytics, name="wa_analytics"),
    path("analytics/digest/<uuid:pk>/", views.wa_digest_detail, name="wa_digest_detail"),
]
