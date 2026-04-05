from django.urls import path

from . import views

app_name = "partners"

urlpatterns = [
    # Public pages
    path("", views.partners_landing, name="landing"),
    path("apply/", views.partners_apply, name="apply"),
    path("articles/<slug:slug>/", views.partners_article, name="article"),
    # Authenticated dashboard
    path("dashboard/", views.partner_dashboard, name="dashboard"),
]
