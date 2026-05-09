from django.urls import path

from apps.calendar_intel import views

app_name = "calendar_intel"

urlpatterns = [
    # Preferences dashboard
    path("preferences/", views.preferences, name="preferences"),

    # HTMX endpoints — preference toggles
    path(
        "htmx/preference/<int:holiday_id>/toggle/",
        views.htmx_preference_toggle,
        name="htmx_preference_toggle",
    ),
    path(
        "htmx/preference/<int:holiday_id>/mute-year/",
        views.htmx_preference_mute_year,
        name="htmx_preference_mute_year",
    ),

    # HTMX widget for Brief
    path("htmx/upcoming/", views.htmx_upcoming, name="htmx_upcoming"),

    # Custom events
    path("custom/add/", views.custom_event_add, name="custom_event_add"),
    path(
        "custom/<int:event_id>/delete/",
        views.custom_event_delete,
        name="custom_event_delete",
    ),
]
