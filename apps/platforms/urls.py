from django.urls import path

from apps.platforms import views

app_name = "platforms"

urlpatterns = [
    path("", views.platform_list, name="list"),
    path("connect/<str:platform>/", views.connect_platform, name="connect"),
    path("callback/<str:platform>/", views.oauth_callback, name="oauth_callback"),
    path("disconnect/<uuid:pk>/", views.disconnect_platform, name="disconnect"),
]
