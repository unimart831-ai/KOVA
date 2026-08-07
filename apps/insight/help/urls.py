from django.urls import path

from . import views

app_name = "help"

urlpatterns = [
    path("", views.help_center, name="center"),
    path("system-maps/", views.system_maps_index, name="system_maps"),
    path("system-maps/print/", views.system_maps_print, name="system_maps_print"),
    path("system-maps/<slug:slug>/", views.system_map_detail, name="system_map"),
    path("<slug:slug>/", views.help_article, name="article"),
]
