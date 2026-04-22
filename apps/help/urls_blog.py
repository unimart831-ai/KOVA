from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.public_blog_index, name="index"),
    path("subscribe/", views.blog_subscribe, name="subscribe"),
    path("unsubscribe/<str:token>/", views.blog_unsubscribe, name="unsubscribe"),
    path("<slug:slug>/", views.public_blog_article, name="article"),
]
