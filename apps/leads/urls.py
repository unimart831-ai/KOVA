from django.urls import path

from apps.leads import views

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
    # Nurture Sequences
    path("nurture/", views.nurture_list, name="nurture_list"),
    path("nurture/create/", views.nurture_create, name="nurture_create"),
    path("nurture/<uuid:sequence_id>/", views.nurture_detail, name="nurture_detail"),
    path("nurture/<uuid:sequence_id>/toggle/", views.nurture_toggle, name="nurture_toggle"),
]
