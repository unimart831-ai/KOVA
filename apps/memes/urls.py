from django.urls import path

from apps.memes import views

app_name = "memes"

urlpatterns = [
    path("", views.meme_discover, name="discover"),
    path("queue/", views.meme_queue, name="queue"),
    path("settings/", views.meme_settings, name="settings"),
    path("<uuid:meme_id>/", views.meme_detail, name="detail"),
    path("<uuid:meme_id>/adapt/", views.meme_adapt, name="adapt"),
    path("<uuid:meme_id>/card/", views.meme_card, name="card"),
    path("adaptation/<uuid:adaptation_id>/approve/", views.meme_approve, name="approve"),
    path("adaptation/<uuid:adaptation_id>/reject/", views.meme_reject, name="reject"),
    path("adaptation/<uuid:adaptation_id>/to-post/", views.meme_to_post, name="to_post"),
    # Trend Alerts
    path("trends/", views.trend_alerts, name="trend_alerts"),
    path("trends/<uuid:pk>/action/", views.trend_alert_action, name="trend_alert_action"),
]
