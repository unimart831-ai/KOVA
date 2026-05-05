from django.urls import path

from apps.briefs import views

app_name = "brief"

urlpatterns = [
    path("", views.brief_home, name="home"),
    path("action/", views.brief_action, name="action"),
    path("dismiss/", views.brief_dismiss_decision, name="dismiss_decision"),
    path("<str:date>/", views.brief_detail, name="detail"),
]
