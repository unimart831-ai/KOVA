from django.urls import path

from apps.platforms import views

app_name = "platforms"

urlpatterns = [
    path("", views.platform_list, name="list"),
    path("connect/<str:platform>/", views.connect_platform, name="connect"),
    path("callback/<str:platform>/", views.oauth_callback, name="oauth_callback"),
    path("disconnect/<uuid:pk>/", views.disconnect_platform, name="disconnect"),
    path("whatsapp/embedded-callback/", views.whatsapp_embedded_callback, name="whatsapp_embedded_callback"),
    path("linkedin/connect-page/", views.linkedin_connect_page, name="linkedin_connect_page"),
    path("linkedin/select-page/", views.linkedin_select_page, name="linkedin_select_page"),
]
