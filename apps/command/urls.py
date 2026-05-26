from django.urls import path

from apps.command import views

app_name = "command"

urlpatterns = [
    path("", views.command_home, name="home"),
    path("standup/", views.command_standup, name="standup"),
    path("moments/", views.command_moments, name="moments"),
    path("listen/", views.command_listen, name="listen"),
]
