from django.urls import path

from apps.calendar_intel import views

app_name = "calendar_intel"

urlpatterns = [
    # Preferences dashboard
    path("preferences/", views.preferences, name="preferences"),
    path(
        "preferences/<int:holiday_id>/refine/",
        views.holiday_refine,
        name="holiday_refine",
    ),

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
        "custom/<int:event_id>/edit/",
        views.custom_event_edit,
        name="custom_event_edit",
    ),
    path(
        "custom/<int:event_id>/delete/",
        views.custom_event_delete,
        name="custom_event_delete",
    ),
]
