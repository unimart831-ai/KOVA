from django.urls import path

from apps.bookings import views

app_name = "bookings"

urlpatterns = [
    path("bookings/", views.bookings_list, name="list"),
    path("bookings/links/new/", views.link_create, name="link_create"),
    path("bookings/links/<uuid:pk>/", views.link_detail, name="link_detail"),
    path("bookings/links/<uuid:pk>/calendar/", views.link_calendar, name="link_calendar"),
    path("bookings/links/<uuid:pk>/slots/", views.slots_for_date, name="slots"),
    path("bookings/<uuid:pk>/", views.booking_detail, name="booking_detail"),
    path("bookings/<uuid:pk>/complete/", views.booking_complete, name="booking_complete"),
    path("bookings/<uuid:pk>/cancel/", views.booking_cancel, name="booking_cancel"),
    # Public booking flow
    path("book/<slug:slug>/", views.public_book, name="public_book"),
    path("book/<slug:slug>/confirm/", views.public_confirm, name="public_confirm"),
    path("book/<slug:slug>/done/<uuid:bid>/", views.public_done, name="public_done"),
]
