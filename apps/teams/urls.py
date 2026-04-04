from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    path("", views.team_list, name="list"),
    path("create/", views.team_create, name="create"),
    path("invite/<str:token>/", views.invitation_accept, name="invitation_accept"),
    path("<slug:slug>/", views.team_detail, name="detail"),
    path("<slug:slug>/invite/", views.team_invite, name="invite"),
    path("<slug:slug>/leave/", views.team_leave, name="leave"),
    path("<slug:slug>/members/<uuid:member_id>/role/", views.member_update_role, name="member_role"),
    path("<slug:slug>/members/<uuid:member_id>/remove/", views.member_remove, name="member_remove"),
    path("<slug:slug>/invitations/<uuid:invitation_id>/cancel/", views.invitation_cancel, name="invitation_cancel"),
    # Brand management
    path("<slug:slug>/brands/create/", views.brand_create, name="brand_create"),
    path("<slug:slug>/brands/<uuid:brand_id>/", views.brand_detail, name="brand_detail"),
    path("<slug:slug>/brands/<uuid:brand_id>/edit/", views.brand_edit, name="brand_edit"),
    path("<slug:slug>/brands/<uuid:brand_id>/toggle/", views.brand_toggle, name="brand_toggle"),
]
