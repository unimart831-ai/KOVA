from django.urls import path

from . import views

app_name = "help"

urlpatterns = [
    path("", views.help_center, name="center"),
    path("<slug:slug>/", views.help_article, name="article"),
]
