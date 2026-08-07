from django.urls import path
from django.views.generic import RedirectView

from apps.messaging.engage import messenger_webhook, views

app_name = "engage"

urlpatterns = [
    path("webhook/messenger/", messenger_webhook.messenger_webhook, name="messenger_webhook"),
    # Hub first — /engage/ lands on Needs reply
    path(
        "",
        RedirectView.as_view(pattern_name="engage:unified_inbox", permanent=False),
        name="inbox_root",
    ),
    path("needs-reply/", views.unified_needs_reply, name="unified_inbox"),
    path("comments/", views.engage_inbox, name="inbox"),
    path("reply/<uuid:pk>/", views.send_reply, name="send_reply"),
    path("trigger/", views.trigger_engage, name="trigger"),
    path("auto-sent/", views.auto_sent_list, name="auto_sent_list"),
    path("auto-sent/<uuid:pk>/undo/", views.auto_sent_undo, name="auto_sent_undo"),
    path("auto-sent/<uuid:pk>/correct/", views.auto_sent_correct, name="auto_sent_correct"),
    path("dms/", views.dm_inbox_view, name="dm_inbox"),
    path("messenger/", views.messenger_threads, name="messenger_threads"),
]
