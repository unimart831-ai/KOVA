from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

from apps.links.views import public_page, public_form_submit, public_link_click
from apps.products.commerce_views import (
    public_commerce_link,
    public_commerce_pay,
    public_shop_index,
)
from apps.products.commerce_sitemap import commerce_sitemap_xml, robots_txt

admin.site.site_header = "KOVA AI ADMIN"
admin.site.site_title = "Kova AI"
admin.site.index_title = "Administration"


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("brief:home")
    from apps.billing.models import get_all_plan_limits
    all_plans = get_all_plan_limits()
    return render(request, "pages/landing.html", {"all_plans": all_plans})


def legal_page(template):
    """Return a view that renders a legal page template."""
    def view(request):
        return render(request, f"pages/{template}")
    return view


def service_worker(request):
    """Serve SW from root so it can control the full scope."""
    from django.contrib.staticfiles import finders
    sw_path = finders.find("sw.js")
    if sw_path:
        with open(sw_path) as f:
            return HttpResponse(f.read(), content_type="application/javascript")
    return HttpResponse(status=404)


def health_check(request):
    """Lightweight health endpoint for Railway + uptime monitors."""
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    # Favicon — redirect to static icon to eliminate 404 noise
    path("favicon.ico", RedirectView.as_view(url="/static/images/icon-192.png", permanent=True)),
    # Health check (before auth — no login required)
    path("health/", health_check, name="health"),
    # Landing
    path("", landing_page, name="landing"),
    # Legal pages
    path("privacy/", legal_page("privacy.html"), name="privacy"),
    path("terms/", legal_page("terms.html"), name="terms"),
    path("cookies/", legal_page("cookies.html"), name="cookies"),
    path("acceptable-use/", legal_page("acceptable_use.html"), name="acceptable_use"),
    path("dpa/", legal_page("dpa.html"), name="dpa"),
    # Campus Rep program (public)
    path("campus-rep/", legal_page("campus_rep.html"), name="campus_rep"),
    # Public help / learn section (no login required)
    path("learn/", include("apps.help.urls_public")),
    # Public SEO blog (Educator agent output — no login required)
    path("blog/", include("apps.help.urls_blog")),
    # Growth Partners (public + authenticated)
    path("partners/", include("apps.partners.urls")),
    # Public Kova Link pages (no login required)
    path("k/<slug:slug>/", public_page, name="public_page"),
    path("k/<slug:slug>/click/<uuid:link_id>/", public_link_click, name="public_link_click"),
    path("k/<slug:slug>/form/<uuid:form_id>/", public_form_submit, name="public_form_submit"),
    # PWA service worker (must be served from root scope)
    path("sw.js", service_worker, name="sw"),
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
    path("emails/", include("apps.emails.urls")),
    path("help/", include("apps.help.urls")),
    path("teams/", include("apps.teams.urls")),
    path("media-queue/", include("apps.media_queue.urls")),
    path("links/", include("apps.links.urls")),
    path("leads/", include("apps.leads.urls")),
    path("products/", include("apps.products.urls")),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", commerce_sitemap_xml, name="sitemap"),
    path(
        "shop/<slug:page_slug>/",
        public_shop_index,
        name="public_shop",
    ),
    path(
        "shop/<slug:page_slug>/<slug:commerce_slug>/",
        public_commerce_link,
        name="public_commerce",
    ),
    path(
        "shop/<slug:page_slug>/<slug:commerce_slug>/pay/",
        public_commerce_pay,
        name="public_commerce_pay",
    ),
    path("campaigns/", include("apps.campaigns.urls")),
    path("whatsapp/", include("apps.whatsapp.urls")),
    path("memes/", include("apps.memes.urls")),
    path("calendar/", include("apps.calendar_intel.urls")),
    path("profile-health/", include("apps.profile_audit.urls")),
    # QR codes + walk-in attribution (Phase 2 W5-6). Mounted at root
    # because it owns both /qr/ and /walkin/ namespaces.
    path("", include("apps.qr_attribution.urls")),
    # Booking integration (Phase 2 W7-8). Owns /bookings/ and /book/.
    path("", include("apps.bookings.urls")),
    # Review request loop (Phase 3 W9). Owns /reviews/.
    path("", include("apps.reviews.urls")),
    # Kova Link Page — public business profile + conversion page.
    path("p/", include("apps.kova_page.urls")),
    path("dashboard/", include("apps.admin_dashboard.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("api/v1/partner/", include("apps.api.partner_urls")),
    # OpenAPI schema + interactive docs
    path("api/schema/", include("apps.api.schema_urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        # path("__debug__/", include("debug_toolbar.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
else:
    # Production: serve user-uploaded / AI-generated media files.
    # When R2 is configured, media URLs are absolute (https://...) and skip this route.
    # This only catches relative /media/... URLs (local FileSystemStorage fallback).
    from django.views.static import serve as static_serve
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
