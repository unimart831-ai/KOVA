from django.urls import path

from apps.engage import views

app_name = "engage"

urlpatterns = [
    path("", views.engage_inbox, name="inbox"),
    path("reply/<uuid:pk>/", views.send_reply, name="send_reply"),
    path("trigger/", views.trigger_engage, name="trigger"),
]
