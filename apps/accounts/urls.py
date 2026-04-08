from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("settings/cta/", views.cta_settings_view, name="cta_settings"),
    path("onboarding/", views.onboarding_view, name="onboarding"),
    path("api/profile-industry/", views.profile_industry_api, name="profile_industry_api"),
]
