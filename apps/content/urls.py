from django.urls import path

from apps.content import views

app_name = "content"

urlpatterns = [
    path("studio/", views.content_studio, name="studio"),
    path("studio/posts/", views.studio_posts, name="studio_posts"),
    path("studio/submit/", views.submit_seed, name="submit_seed"),
    path("studio/dismiss-failed/", views.dismiss_failed_seeds, name="dismiss_failed"),
    path("studio/seed/<uuid:seed_id>/status/", views.seed_status, name="seed_status"),
    path("studio/seed/<uuid:seed_id>/batch-approve/", views.batch_approve, name="batch_approve"),
    path("queue/", views.content_queue, name="queue"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("<uuid:post_id>/edit/", views.edit_post, name="edit"),
    path("<uuid:post_id>/approve/", views.approve_post, name="approve"),
    path("<uuid:post_id>/reject/", views.reject_post, name="reject"),
    path("<uuid:post_id>/regenerate/", views.regenerate_post, name="regenerate"),
    path("<uuid:post_id>/upload/", views.upload_media, name="upload_media"),
    path("<uuid:post_id>/", views.post_detail, name="post_detail"),
]
