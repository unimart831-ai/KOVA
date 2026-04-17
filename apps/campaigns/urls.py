from django.urls import path

from apps.campaigns import views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="list"),
    path("create/", views.campaign_create, name="create"),
    path("<uuid:pk>/", views.campaign_detail, name="detail"),
    path("<uuid:pk>/edit/", views.campaign_edit, name="edit"),
    path("<uuid:pk>/status/", views.campaign_status, name="status"),
    path("<uuid:pk>/delete/", views.campaign_delete, name="delete"),
    path("<uuid:pk>/add-seed/", views.campaign_add_seed, name="add_seed"),
    path("<uuid:pk>/remove-seed/<uuid:seed_pk>/", views.campaign_remove_seed, name="remove_seed"),
    path("<uuid:pk>/add-email/", views.campaign_add_email, name="add_email"),
    path("<uuid:pk>/remove-email/<uuid:email_pk>/", views.campaign_remove_email, name="remove_email"),
    path("<uuid:pk>/add-note/", views.campaign_add_note, name="add_note"),
    path("ai-build/", views.campaign_ai_build, name="ai_build"),
]
