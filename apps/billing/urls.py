from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("", views.billing_overview, name="overview"),
]
