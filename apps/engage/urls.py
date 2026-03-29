from django.urls import path

from apps.engage import views

app_name = "engage"

urlpatterns = [
    path("", views.engage_inbox, name="inbox"),
]
