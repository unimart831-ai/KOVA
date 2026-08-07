from django.urls import path

from . import views

app_name = "learn"

urlpatterns = [
    path("", views.public_help_center, name="center"),
    path("<slug:slug>/", views.public_help_article, name="article"),
]
