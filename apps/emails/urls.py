from django.urls import path

from apps.emails import marketing_views, views

app_name = "emails"

urlpatterns = [
    # Public one-click unsubscribe (no login required)
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),

    # Resend delivery webhooks
    path("webhooks/resend/", views.resend_webhook, name="resend_webhook"),

    # Email marketing dashboard
    path("marketing/", marketing_views.email_dashboard, name="dashboard"),

    # Subscribers
    path("subscribers/", marketing_views.subscriber_list, name="subscribers"),
    path("subscribers/add/", marketing_views.subscriber_add, name="subscriber_add"),

    # Lists
    path("lists/", marketing_views.list_index, name="lists"),
    path("lists/create/", marketing_views.list_create, name="list_create"),
    path("lists/<uuid:list_id>/", marketing_views.list_detail, name="list_detail"),
    path("lists/<uuid:list_id>/edit/", marketing_views.list_edit, name="list_edit"),

    # Campaigns
    path("campaigns/", marketing_views.campaign_list, name="campaigns"),
    path("campaigns/create/", marketing_views.campaign_create, name="campaign_create"),
    path("campaigns/<uuid:campaign_id>/", marketing_views.campaign_detail, name="campaign_detail"),
    path("campaigns/<uuid:campaign_id>/edit/", marketing_views.campaign_edit, name="campaign_edit"),
    path("campaigns/<uuid:campaign_id>/send/", marketing_views.campaign_send, name="campaign_send"),

    # Sequences
    path("sequences/", marketing_views.sequence_list, name="sequences"),
    path("sequences/<uuid:sequence_id>/", marketing_views.sequence_detail, name="sequence_detail"),
]
