from django.urls import path

from apps.commerce.reviews import views

app_name = "reviews"

urlpatterns = [
    path("reviews/", views.reviews_list, name="list"),
    path("reviews/<uuid:pk>/", views.review_detail, name="detail"),
    path("reviews/<uuid:pk>/respond/", views.capture_response, name="respond"),
]
