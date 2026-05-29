from django.urls import path

from apps.engage import views

app_name = "engage"

urlpatterns = [
    path("", views.engage_inbox, name="inbox"),
    path("reply/<uuid:pk>/", views.send_reply, name="send_reply"),
    path("trigger/", views.trigger_engage, name="trigger"),
    # Engage Agent v2 — recent auto-sends + undo + correction (Phase 1 W2)
    path("auto-sent/", views.auto_sent_list, name="auto_sent_list"),
    path("auto-sent/<uuid:pk>/undo/", views.auto_sent_undo, name="auto_sent_undo"),
    path("auto-sent/<uuid:pk>/correct/", views.auto_sent_correct, name="auto_sent_correct"),
    # Phase 5 — Unified DM inbox
    path("dms/", views.dm_inbox_view, name="dm_inbox"),
]
