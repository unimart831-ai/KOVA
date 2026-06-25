from django.urls import path

from apps.profile_audit import views

app_name = "profile_audit"

urlpatterns = [
    path("", views.audit_list, name="list"),
    path("<uuid:account_id>/", views.audit_detail, name="detail"),
]
