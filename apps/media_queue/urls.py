from django.urls import path

from . import views

app_name = "media_queue"

urlpatterns = [
    # Queue management
    path("", views.queue_list, name="list"),
    path("create/", views.queue_create, name="create"),
    path("<uuid:queue_id>/", views.queue_detail, name="detail"),
    path("<uuid:queue_id>/settings/", views.queue_settings, name="settings"),
    path("<uuid:queue_id>/toggle/", views.queue_toggle, name="toggle"),
    path("<uuid:queue_id>/delete/", views.queue_delete, name="delete"),

    # Bulk upload + reorder
    path("<uuid:queue_id>/upload/", views.queue_upload, name="upload"),
    path("<uuid:queue_id>/reorder/", views.queue_reorder, name="reorder"),

    # Individual items
    path("item/<uuid:item_id>/edit/", views.item_edit, name="item_edit"),
    path("item/<uuid:item_id>/delete/", views.item_delete, name="item_delete"),
    path("item/<uuid:item_id>/retry/", views.item_retry, name="item_retry"),
]
