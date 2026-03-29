from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("bell/", views.notification_bell, name="bell"),
    path("dropdown/", views.notification_dropdown, name="dropdown"),
    path("mark-all-read/", views.mark_all_read, name="mark_all_read"),
]
