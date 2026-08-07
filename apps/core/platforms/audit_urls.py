"""URL namespace profile_audit — kept for template {% url %} compatibility."""

from django.urls import path

from apps.core.platforms import audit_views

app_name = "profile_audit"

urlpatterns = [
    path("", audit_views.audit_list, name="list"),
    path("<uuid:account_id>/", audit_views.audit_detail, name="detail"),
]
