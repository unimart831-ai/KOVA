from django.urls import path

from apps.commerce.leads import views

app_name = "leads"

urlpatterns = [
    path("", views.lead_list, name="list"),
    path("pipeline/", views.lead_pipeline, name="pipeline"),
    path("create/", views.lead_create, name="create"),
    path("analytics/", views.lead_analytics, name="analytics"),
    path("<uuid:lead_id>/", views.lead_detail, name="detail"),
    path("<uuid:lead_id>/edit/", views.lead_edit, name="edit"),
    path("<uuid:lead_id>/status/", views.lead_change_status, name="change_status"),
    path("<uuid:lead_id>/note/", views.lead_add_note, name="add_note"),
    path("<uuid:lead_id>/tag/", views.lead_add_tag, name="add_tag"),
    path("<uuid:lead_id>/tag/remove/", views.lead_remove_tag, name="remove_tag"),
]
