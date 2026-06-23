from django.urls import path

from apps.calendar_intel import views

app_name = "calendar_intel"

urlpatterns = [
    path("preferences/", views.preferences, name="preferences"),
]
