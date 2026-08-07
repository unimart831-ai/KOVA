from django.urls import path

from apps.commerce.links import views

app_name = "links"

urlpatterns = [
    # Dashboard (authenticated)
    path("", views.page_list, name="list"),
    path("create/", views.page_create, name="page_create"),
    path("<uuid:page_id>/", views.page_detail, name="page_detail"),
    path("<uuid:page_id>/edit/", views.page_edit, name="page_edit"),
    path("<uuid:page_id>/delete/", views.page_delete, name="page_delete"),

    # Links CRUD
    path("<uuid:page_id>/links/add/", views.link_add, name="link_add"),
    path("<uuid:page_id>/links/<uuid:link_id>/edit/", views.link_edit, name="link_edit"),
    path("<uuid:page_id>/links/<uuid:link_id>/delete/", views.link_delete, name="link_delete"),

    # Form CRUD
    path("<uuid:page_id>/forms/add/", views.form_add, name="form_add"),
    path("<uuid:page_id>/forms/<uuid:form_id>/edit/", views.form_edit, name="form_edit"),
    path("<uuid:page_id>/forms/<uuid:form_id>/delete/", views.form_delete, name="form_delete"),

    # Submissions
    path("submissions/", views.submissions_list, name="submissions"),
    path("submissions/<uuid:submission_id>/read/", views.submission_mark_read, name="submission_mark_read"),
]
