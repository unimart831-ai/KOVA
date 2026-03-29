from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import render, redirect
from django.urls import include, path


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("brief:home")
    return render(request, "pages/landing.html")


urlpatterns = [
    # Landing
    path("", landing_page, name="landing"),
    # Admin
    path("admin/", admin.site.urls),
    # Auth (allauth)
    path("accounts/", include("allauth.urls")),
    # App URLs
    path("accounts/", include("apps.accounts.urls")),
    path("brief/", include("apps.briefs.urls")),
    path("content/", include("apps.content.urls")),
    path("platforms/", include("apps.platforms.urls")),
    path("agents/", include("apps.agents.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("engage/", include("apps.engage.urls")),
    path("billing/", include("apps.billing.urls")),
    path("notifications/", include("apps.notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        # path("__debug__/", include("debug_toolbar.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
