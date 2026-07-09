from django.urls import path
from django.views.generic import RedirectView

from apps.content import views

app_name = "content"

urlpatterns = [
    path("create/", RedirectView.as_view(pattern_name="content:studio", permanent=False), name="create"),
    path("studio/", views.content_studio, name="studio"),
    path("studio/posts/", views.studio_posts, name="studio_posts"),
    path("studio/submit/", views.submit_seed, name="submit_seed"),
    path("studio/upload-reel/", views.upload_reel, name="upload_reel"),
    path("studio/voice/", views.voice_to_seed, name="voice_to_seed"),
    path("studio/dismiss-failed/", views.dismiss_failed_seeds, name="dismiss_failed"),
    path("studio/refresh-suggestions/", views.refresh_suggestions, name="refresh_suggestions"),
    path("studio/seed/<uuid:seed_id>/status/", views.seed_status, name="seed_status"),
    path("studio/seed/<uuid:seed_id>/generation-status/", views.seed_generation_status, name="seed_generation_status"),
    path("studio/seed/<uuid:seed_id>/batch-approve/", views.batch_approve, name="batch_approve"),
    path("studio/campaign/<uuid:campaign_id>/approve/", views.campaign_approve, name="campaign_approve"),
    path("studio/campaign/<uuid:campaign_id>/client-request/", views.campaign_request_client_approval, name="campaign_client_request"),
    path("studio/campaign/<uuid:campaign_id>/client-approve/", views.campaign_client_approve, name="campaign_client_approve"),
    path("campaigns/asset/<uuid:asset_id>/proposals/", views.asset_campaign_proposals, name="asset_proposals"),
    path("campaigns/asset/<uuid:asset_id>/activate/", views.activate_campaign_proposal, name="activate_proposal"),
    path("queue/", views.content_queue, name="queue"),
    path("queue/sections/", views.queue_sections, name="queue_sections"),
    path("queue/clear-failed/", views.clear_failed_posts, name="clear_failed_posts"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar/grid/", views.content_calendar_grid, name="calendar_grid"),
    # Post actions
    path("<uuid:post_id>/edit/", views.edit_post, name="edit"),
    path("<uuid:post_id>/reschedule/", views.reschedule_post, name="reschedule"),
    path("<uuid:post_id>/approve/", views.approve_post, name="approve"),
    path("<uuid:post_id>/republish/", views.republish_post, name="republish"),
    path("<uuid:post_id>/reject/", views.reject_post, name="reject"),
    path("<uuid:post_id>/delete/", views.delete_post, name="delete_post"),
    path("<uuid:post_id>/regenerate/", views.regenerate_post, name="regenerate"),
    path("<uuid:post_id>/regenerate/status/", views.regenerate_status, name="regenerate_status"),
    path("<uuid:post_id>/preview/", views.post_preview, name="preview"),
    path("<uuid:post_id>/rate/", views.rate_post, name="rate"),
    path("<uuid:post_id>/upload/", views.upload_media, name="upload_media"),
    path("<uuid:post_id>/card-upload/", views.card_upload_media, name="card_upload_media"),
    path("<uuid:post_id>/clear-media/", views.clear_ai_media, name="clear_ai_media"),
    path("<uuid:post_id>/retry-image/", views.retry_image, name="retry_image"),
    path("<uuid:post_id>/retry-reel/", views.retry_reel, name="retry_reel"),
    path("<uuid:post_id>/retry-publish/", views.retry_publish, name="retry_publish"),
    path("<uuid:post_id>/reschedule-rate-limited/", views.reschedule_rate_limited, name="reschedule_rate_limited"),
    path("<uuid:post_id>/slides/", views.update_carousel_slides, name="update_slides"),
    path("<uuid:post_id>/generate-image/", views.generate_image, name="generate_image"),
    path("<uuid:post_id>/regenerate-image/", views.regenerate_image, name="regenerate_image"),
    path("<uuid:post_id>/media/<uuid:attachment_id>/delete/", views.delete_media, name="delete_media"),
    path("<uuid:post_id>/card/", views.post_card, name="post_card"),
    path("<uuid:post_id>/", views.post_detail, name="post_detail"),
]
