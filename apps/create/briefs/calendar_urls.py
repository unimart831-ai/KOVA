"""URL namespace calendar_intel — kept for template {% url %} compatibility."""

from django.urls import path

from apps.create.briefs import calendar_views

app_name = "calendar_intel"

urlpatterns = [
    path("preferences/", calendar_views.preferences, name="preferences"),
]
