from django.urls import path

from apps.whatsapp import views, webhook

app_name = "whatsapp"

urlpatterns = [
    # Webhook (Meta sends events here — GET for verification, POST for events)
    path("webhook/", webhook.whatsapp_webhook, name="webhook"),

    # ── Inbox (Sprint 5A) ────────────────────────────────────────────────
    path("", views.whatsapp_inbox, name="inbox"),
    path("conversation/<uuid:pk>/", views.whatsapp_conversation, name="conversation"),
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

    # ── Broadcasts & Sequences (Sprint 5D) ───────────────────────────────
    path("broadcasts/", views.broadcast_list, name="broadcast_list"),
    path("broadcasts/create/", views.broadcast_create, name="broadcast_create"),
    path("broadcasts/<uuid:pk>/", views.broadcast_detail, name="broadcast_detail"),
    path("broadcasts/<uuid:pk>/launch/", views.broadcast_launch, name="broadcast_launch"),
    path("broadcasts/<uuid:pk>/pause/", views.broadcast_pause, name="broadcast_pause"),
    path("sequences/create/", views.sequence_create, name="sequence_create"),
    path("sequences/<uuid:pk>/", views.sequence_detail, name="sequence_detail"),
    path("sequences/<uuid:pk>/add-step/", views.sequence_add_step, name="sequence_add_step"),
    path("sequences/<uuid:pk>/toggle/", views.sequence_toggle, name="sequence_toggle"),

    # ── Analytics (Sprint 5D) ────────────────────────────────────────────
    path("analytics/", views.wa_analytics, name="wa_analytics"),
    path("analytics/digest/<uuid:pk>/", views.wa_digest_detail, name="wa_digest_detail"),

    # ── Channels (Sprint 5E) ─────────────────────────────────────────────
    path("channels/", views.channel_dashboard, name="channel_dashboard"),
    path("channels/create/", views.channel_create, name="channel_create"),
    path("channels/<uuid:pk>/", views.channel_detail, name="channel_detail"),
    path("channels/<uuid:pk>/post/", views.channel_post_create, name="channel_post_create"),
    path("channels/<uuid:pk>/post/<uuid:post_pk>/publish/", views.channel_post_publish, name="channel_post_publish"),
    path("channels/<uuid:pk>/toggle-curate/", views.channel_toggle_curate, name="channel_toggle_curate"),
]
