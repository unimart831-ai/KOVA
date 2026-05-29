from django.urls import path

from apps.briefs import views

app_name = "brief"

urlpatterns = [
    path("", views.brief_home, name="home"),
    path("operations-report/", views.operations_report_partial, name="operations_report"),
    path("action/", views.brief_action, name="action"),
    path("dismiss/", views.brief_dismiss_decision, name="dismiss_decision"),
    path("archive/", views.brief_archive_list, name="archive"),
    path("archive-toggle/", views.archive_brief, name="archive_toggle"),
    path("<str:date>/", views.brief_detail, name="detail"),
]
