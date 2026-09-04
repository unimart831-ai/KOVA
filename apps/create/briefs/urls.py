from django.urls import path

from apps.create.briefs import views

app_name = "brief"

urlpatterns = [
    path("", views.brief_home, name="home"),
    path("operations-report/", views.operations_report_partial, name="operations_report"),
    path("action/", views.brief_action, name="action"),
    path("dismiss/", views.brief_dismiss_decision, name="dismiss_decision"),
    # History (archive / past-day detail) — wire when user histories ship
]
