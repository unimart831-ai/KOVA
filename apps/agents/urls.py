from django.urls import path

from apps.agents import views

app_name = "agents"

urlpatterns = [
    path("", views.agent_control, name="control"),
    path("activity/", views.agent_activity_log, name="activity_log"),
    path("<str:slug>/", views.agent_detail, name="detail"),
    path("<str:slug>/toggle/", views.agent_toggle, name="toggle"),
    path("<str:slug>/status/", views.agent_status, name="status"),
    path("<str:slug>/instructions/", views.agent_update_instructions, name="update_instructions"),
]
