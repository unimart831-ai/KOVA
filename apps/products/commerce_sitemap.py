"""Sitemap and robots helpers for public commerce pages."""

from __future__ import annotations

from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.products.commerce_links import commerce_link_path, resolve_page_slug, shop_index_path
from apps.products.models import Product


def _absolute_url(request, path: str) -> str:
    return request.build_absolute_uri(path)


def commerce_sitemap_xml(request) -> HttpResponse:
    """Dynamic sitemap for public shop index and product pages."""
    today = timezone.now().date().isoformat()
    urls: list[tuple[str, str, str]] = []

    profiles = UserProfile.objects.select_related("user").filter(
        page_slug__isnull=False,
    ).exclude(page_slug="")

    seen_shops: set[str] = set()
    for profile in profiles:
        page_slug = resolve_page_slug(profile)
        if page_slug in seen_shops:
            continue

        products = Product.objects.filter(
            user=profile.user,
            is_active=True,
        ).exclude(commerce_slug="").only("commerce_slug", "updated_at")

        if not products.exists():
            continue

        seen_shops.add(page_slug)
        shop_path = shop_index_path(profile)
        urls.append((_absolute_url(request, shop_path), today, "weekly"))

        for product in products:
            path = commerce_link_path(product, profile)
            lastmod = product.updated_at.date().isoformat() if product.updated_at else today
            urls.append((_absolute_url(request, path), lastmod, "weekly"))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, changefreq in urls:
        lines.extend([
            "  <url>",
            f"    <loc>{escape(loc)}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            f"    <changefreq>{changefreq}</changefreq>",
            "  </url>",
        ])
    lines.append("</urlset>")

    return HttpResponse("\n".join(lines), content_type="application/xml")


def robots_txt(request) -> HttpResponse:
    sitemap_url = _absolute_url(request, "/sitemap.xml")
    lines = [
        "User-agent: *",
        "Allow: /shop/",
        "Allow: /blog/",
        "Allow: /learn/",
        "Allow: /k/",
        "Allow: /p/",
        "Disallow: /brief/",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /dashboard/",
        "Disallow: /api/",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
