from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

from apps.commerce.links.views import public_page, public_form_submit, public_link_click
from apps.commerce.products.commerce_views import (
    commerce_payment_status,
    public_commerce_link,
    public_commerce_pay,
    public_shop_index,
    public_whatsapp_order,
)
from apps.create.content.views.campaign_pages import public_campaign_page
from apps.commerce.products.commerce_sitemap import commerce_sitemap_xml, robots_txt
from apps.core.accounts.legal_views import legal
from apps.core.platforms.facebook_data_deletion_views import (
    facebook_data_deletion_instructions,
    facebook_data_deletion_status,
)

admin.site.site_header = "KOVA AI ADMIN"
admin.site.site_title = "Kova AI"
admin.site.index_title = "Administration"


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("brief:home")
    from apps.core.billing.models import (
        TRIAL_CAMPAIGN_LIMIT,
        get_campaign_addon_packs,
        get_plan_limits,
        get_public_plan_limits,
    )
    kova = get_plan_limits("kova")
    return render(request, "landing/landing.html", {
        "all_plans": get_public_plan_limits(),
        "kova_plan": kova,
        "campaign_addons": get_campaign_addon_packs(),
        "agency_plan": get_plan_limits("agency"),
        "trial_days": kova.get("trial_days", 7),
        "trial_campaigns": TRIAL_CAMPAIGN_LIMIT,
    })


def landing_start(request):
    """Hero CTA → signup (no session prefill)."""
    return redirect("account_signup")


_COMPARE_TEMPLATES = {
    "buffer": "pages/compare_buffer.html",
    "manual": "pages/compare_manual.html",
    "nas": "pages/compare_nas.html",
}


def pricing(request) -> HttpResponse:
    from apps.core.billing.models import (
        TRIAL_CAMPAIGN_LIMIT,
        get_campaign_addon_packs,
        get_plan_limits,
    )
    kova = get_plan_limits("kova")
    return render(request, "pages/pricing.html", {
        "kova_plan": kova,
        "campaign_addons": get_campaign_addon_packs(),
        "agency_plan": get_plan_limits("agency"),
        "trial_days": kova.get("trial_days", 7),
        "trial_campaigns": TRIAL_CAMPAIGN_LIMIT,
    })

def compare_page(request, slug):
    template = _COMPARE_TEMPLATES.get(slug)
    if not template:
        return redirect("landing")
    from apps.core.billing.models import get_public_plan_limits
    return render(request, template, {"all_plans": get_public_plan_limits()})


def service_worker(request):
    """
    Serve SW from root so it can control the full scope.
    """
    from django.contrib.staticfiles import finders
    sw_path = finders.find("sw.js")
    if sw_path:
        with open(sw_path) as f:
            return HttpResponse(f.read(), content_type="application/javascript")
    return HttpResponse(status=404)


def health_check(request):
    """Lightweight health endpoint for Railway + uptime monitors."""
    return HttpResponse("ok", content_type="text/plain")


def health_check_deep(request):
    """Deep probe — DB, Redis, Celery broker, media/LLM keys."""
    from django.http import JsonResponse

    from apps.core.system.health_checks import run_health_checks

    report = run_health_checks(deep=True)
    status = 200 if report.get("ok") else 503
    return JsonResponse(report, status=status)


urlpatterns = [
    # Favicon — redirect to static icon to eliminate 404 noise
    path("favicon.ico", RedirectView.as_view(url="/static/images/icon-192.png", permanent=True)),
    # Health check (before auth — no login required)
    path("health/", health_check, name="health"),
    path("health/deep/", health_check_deep, name="health_deep"),
    # Landing
    path("", landing_page, name="landing"),
    path("pricing/", pricing, name="pricing"),
    path("start/", landing_start, name="landing_start"),
    path("compare/<slug:slug>/", compare_page, name="compare"),
    # Legal — Meta deletion first (dynamic), then static /legal/<name>/
    path(
        "legal/facebook-data-deletion/",
        facebook_data_deletion_instructions,
        name="facebook_data_deletion",
    ),
    path(
        "legal/facebook-data-deletion/status/<str:confirmation_code>/",
        facebook_data_deletion_status,
        name="facebook_data_deletion_status",
    ),
    path("legal/<slug:name>/", legal, name="legal"),
    # Legacy legal URLs → /legal/<name>/
    path("privacy/", RedirectView.as_view(url="/legal/privacy/", permanent=True)),
    path("terms/", RedirectView.as_view(url="/legal/terms/", permanent=True)),
    path("cookies/", RedirectView.as_view(url="/legal/cookies/", permanent=True)),
    path("acceptable-use/", RedirectView.as_view(url="/legal/acceptable-use/", permanent=True)),
    path("dpa/", RedirectView.as_view(url="/legal/dpa/", permanent=True)),
    path("privacy/data-deletion/", RedirectView.as_view(pattern_name="facebook_data_deletion",permanent=False), name="privacy_data_deletion", ),
    
    # Public help / learn section (no login required)
    path("learn/", include("apps.insight.help.urls_public")),
    # Public SEO blog (Educator agent output — no login required)
    path("blog/", include("apps.insight.help.urls_blog")),
    # Public Kova Link pages (no login required)
    path("k/<slug:slug>/", public_page, name="public_page"),
    path("k/<slug:slug>/click/<uuid:link_id>/", public_link_click, name="public_link_click"),
    path("k/<slug:slug>/form/<uuid:form_id>/", public_form_submit, name="public_form_submit"),
    # PWA service worker (must be served from root scope)
    path("sw.js", service_worker, name="sw"),
    # Admin
    path("admin/", admin.site.urls),
    # Kova accounts routes before allauth so /accounts/facebook/login/ uses platform OAuth
    path("accounts/", include("apps.core.accounts.urls")),
    # Auth (allauth) — legacy social callbacks; after apps.core.accounts for path precedence
    path("accounts/", include("allauth.urls")),
    path("brief/", include("apps.create.briefs.urls")),
    path("calendar/", include("apps.create.briefs.calendar_urls")),
    path("content/", include("apps.create.content.urls")),
    path("platforms/", include("apps.core.platforms.urls")),
    path("profile-audit/", include("apps.core.platforms.audit_urls")),
    path("agents/", include("apps.create.agents.urls")),
    path("analytics/", include("apps.insight.analytics.urls")),
    path("billing/", include("apps.core.billing.urls")),
    path("notifications/", include("apps.messaging.notifications.urls")),
    path("emails/", include("apps.messaging.emails.urls")),
    path("help/", include("apps.insight.help.urls")),
    path("links/", include("apps.commerce.links.urls")),
    path("leads/", include("apps.commerce.leads.urls")),
    path("products/", include("apps.commerce.products.urls")),
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
    path(
        "shop/payment/<uuid:payment_id>/status/",
        commerce_payment_status,
        name="commerce_payment_status",
    ),
    path(
        "c/<slug:campaign_slug>/",
        public_campaign_page,
        name="public_campaign",
    ),
    path(
        "commerce/wa-order/",
        public_whatsapp_order,
        name="public_whatsapp_order",
    ),
    path("whatsapp/", include("apps.messaging.whatsapp.urls")),
    path("p/", include("apps.commerce.links.hub.urls")),
    path("dashboard/", include("apps.core.admin_dashboard.urls")),
    path("api/v1/", include("apps.insight.api.urls")),
    # OpenAPI schema + interactive docs
    path("api/schema/", include("apps.insight.api.schema_urls")),
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
