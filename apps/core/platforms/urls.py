from django.urls import path

from apps.core.platforms import views
from apps.core.platforms.facebook_data_deletion_views import (
    facebook_data_deletion_callback,
    facebook_data_deletion_callback_probe,
)

app_name = "platforms"

urlpatterns = [
    path(
        "facebook/data-deletion/",
        facebook_data_deletion_callback,
        name="facebook_data_deletion_callback",
    ),
    path(
        "facebook/data-deletion/probe/",
        facebook_data_deletion_callback_probe,
        name="facebook_data_deletion_callback_probe",
    ),
    path("", views.platform_list, name="list"),
    path("connect/<str:platform>/", views.connect_platform, name="connect"),
    path("callback/<str:platform>/", views.oauth_callback, name="oauth_callback"),
    path("disconnect/<uuid:pk>/", views.disconnect_platform, name="disconnect"),
    path("whatsapp/embedded-callback/", views.whatsapp_embedded_callback, name="whatsapp_embedded_callback"),
    path("facebook/<uuid:pk>/select-page/", views.facebook_select_page, name="facebook_select_page"),
]
