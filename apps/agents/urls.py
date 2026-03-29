from django.urls import path

from apps.agents import views

app_name = "agents"

urlpatterns = [
    path("", views.agent_control, name="control"),
    path("<str:slug>/toggle/", views.agent_toggle, name="toggle"),
    path("<str:slug>/status/", views.agent_status, name="status"),
]
