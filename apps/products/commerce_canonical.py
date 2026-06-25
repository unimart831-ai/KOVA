"""
Canonical public commerce URLs — one handle per business.

Bio link, social CTAs, and legacy /k/ pages resolve to /shop/<page_slug>/ when
the seller has an active commerce catalog.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def user_has_commerce_shop(user) -> bool:
    """True when the business has at least one active product on the public shop."""
    from apps.products.models import Product

    return Product.objects.filter(
        user=user,
        is_active=True,
    ).exclude(commerce_slug="").exists()


def canonical_shop_path(profile) -> str:
    from apps.products.commerce_links import resolve_page_slug

    return f"/shop/{resolve_page_slug(profile)}/"


def canonical_shop_url(profile, request=None) -> str:
    path = canonical_shop_path(profile)
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site}{path}" if site else path


def canonical_business_url(user, profile=None, request=None) -> str:
    """
    Primary public URL for a business — shop when catalog exists, else Kova Page.
    """
    profile = profile or user.profile
    if user_has_commerce_shop(user):
        return canonical_shop_url(profile, request)
    page = primary_kova_page(user)
    if page:
        path = page.get_absolute_url()
        if request:
            return request.build_absolute_uri(path)
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        return f"{site}{path}" if site else path
    if profile.page_slug:
        return canonical_shop_url(profile, request)
    return ""


def primary_kova_page(user):
    from apps.links.models import KovaPage

    return (
        KovaPage.objects.filter(user=user, is_published=True)
        .order_by("-created_at")
        .first()
    )


def commerce_shop_redirect_path(page) -> str | None:
    """Permanent redirect target for /k/<slug>/ when a commerce shop is live."""
    if not user_has_commerce_shop(page.user):
        return None
    return canonical_shop_path(page.user.profile)


def _link_public_href(link, page_slug: str) -> str:
    from apps.links.models import KovaLink

    if link.link_type == KovaLink.LinkType.HEADER:
        return ""
    if link.link_type in (KovaLink.LinkType.URL, KovaLink.LinkType.SOCIAL) and link.url:
        return reverse(
            "public_link_click",
            kwargs={"slug": page_slug, "link_id": link.pk},
        )
    if link.link_type == KovaLink.LinkType.EMAIL and link.url:
        return f"mailto:{link.url.strip()}"
    if link.link_type == KovaLink.LinkType.PHONE and link.url:
        raw = link.url.strip()
        if raw.startswith("+"):
            return f"tel:{raw}"
        return f"tel:{raw}"
    return (link.url or "").strip()


def build_unified_shop_footer(profile, user, request=None) -> dict:
    """
    Shop footer: hours/delivery + Kova Page links and lead forms merged in.
    """
    from apps.links.forms import PublicFormSubmissionForm
    from apps.links.models import KovaLink
    from apps.products.storefront import shop_footer_data

    base = shop_footer_data(profile)
    page = primary_kova_page(user)
    kova_links: list[dict] = []
    kova_forms: list[dict] = []
    active_form = None
    form_instance = None

    if page:
        shop_url = canonical_shop_path(profile)
        for link in page.links.filter(is_active=True).order_by("order", "-created_at"):
            if link.link_type == KovaLink.LinkType.HEADER:
                continue
            href = _link_public_href(link, page.slug)
            if not href:
                continue
            if link.url and shop_url in link.url:
                continue
            kova_links.append({
                "id": str(link.pk),
                "title": link.title,
                "url": href,
                "icon": link.icon or "",
                "featured": link.is_featured,
                "external": href.startswith(("http://", "https://", "mailto:", "tel:")),
            })

        for form in page.forms.filter(is_active=True).order_by("-created_at"):
            kova_forms.append({
                "id": str(form.pk),
                "title": form.title,
                "description": form.description,
                "button_text": form.button_text,
                "submit_path": reverse(
                    "public_form_submit",
                    kwargs={"slug": page.slug, "form_id": form.pk},
                ),
            })

        first_form = page.forms.filter(is_active=True).first()
        if first_form:
            active_form = first_form
            form_instance = PublicFormSubmissionForm()
            if not first_form.show_name_field:
                form_instance.fields.pop("name", None)
            if not first_form.show_phone_field:
                form_instance.fields.pop("phone", None)
            if not first_form.show_message_field:
                form_instance.fields.pop("message", None)

    kova_form_submit_path = ""
    if active_form and page:
        kova_form_submit_path = reverse(
            "public_form_submit",
            kwargs={"slug": page.slug, "form_id": active_form.pk},
        )

    return {
        **base,
        "canonical_shop_url": canonical_shop_url(profile, request),
        "kova_page_slug": page.slug if page else "",
        "kova_page_title": page.title if page else "",
        "kova_page_bio": (page.bio or "").strip() if page else "",
        "kova_links": kova_links,
        "kova_forms": kova_forms,
        "kova_active_form": active_form,
        "kova_form_instance": form_instance,
        "kova_form_submit_path": kova_form_submit_path,
        "has_kova_extras": bool(kova_links or kova_forms),
    }
