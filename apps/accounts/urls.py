from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("settings/cta/", views.cta_settings_view, name="cta_settings"),
    path("settings/emergency-pause/", views.toggle_emergency_pause, name="emergency_pause"),
    path("onboarding/", views.onboarding_view, name="onboarding"),
    path("onboarding/complete/", views.onboarding_complete, name="onboarding_complete"),
    path("onboarding/progress/", views.onboarding_progress_api, name="onboarding_progress"),
    path("api/profile-industry/", views.profile_industry_api, name="profile_industry_api"),
    path("api/ai-brand-builder/", views.ai_brand_builder, name="ai_brand_builder"),
]
