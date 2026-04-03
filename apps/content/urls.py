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
    # A/B Testing
    path("ab-tests/", views.ab_test_list, name="ab_test_list"),
    path("ab-tests/create/", views.ab_test_create, name="ab_test_create"),
    path("ab-tests/<uuid:test_id>/", views.ab_test_detail, name="ab_test_detail"),
    path("ab-tests/<uuid:test_id>/start/", views.ab_test_start, name="ab_test_start"),
    path("ab-tests/<uuid:test_id>/conclude/", views.ab_test_conclude, name="ab_test_conclude"),
    path("ab-tests/<uuid:test_id>/cancel/", views.ab_test_cancel, name="ab_test_cancel"),
    # Post actions
    path("<uuid:post_id>/edit/", views.edit_post, name="edit"),
    path("<uuid:post_id>/approve/", views.approve_post, name="approve"),
    path("<uuid:post_id>/reject/", views.reject_post, name="reject"),
    path("<uuid:post_id>/regenerate/", views.regenerate_post, name="regenerate"),
    path("<uuid:post_id>/preview/", views.post_preview, name="preview"),
    path("<uuid:post_id>/upload/", views.upload_media, name="upload_media"),
    path("<uuid:post_id>/", views.post_detail, name="post_detail"),
]
