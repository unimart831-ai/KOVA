from django.urls import path

from apps.profile_audit import views

app_name = "profile_audit"

urlpatterns = [
    path("", views.health_list, name="list"),
    path("<uuid:account_id>/", views.health_detail, name="detail"),
    path("<uuid:account_id>/reaudit/", views.reaudit_account, name="reaudit"),
    path("suggestions/<int:suggestion_id>/approve/", views.suggestion_approve, name="approve"),
    path("suggestions/<int:suggestion_id>/dismiss/", views.suggestion_dismiss, name="dismiss"),
]
