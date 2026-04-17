from django.urls import path

from apps.briefs import views

app_name = "brief"

urlpatterns = [
    path("", views.brief_home, name="home"),
    path("action/", views.brief_action, name="action"),
]
