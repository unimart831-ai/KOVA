"""
Kova Link Page — public conversion page per business.

Public:
  page_view      GET  /p/<slug>/         — anyone with the link
  page_contact   POST /p/<slug>/contact/ — contact form → Lead
"""
from __future__ import annotations

from urllib.parse import quote

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import UserProfile


@require_GET
def page_view(request, slug):
    profile = get_object_or_404(UserProfile, page_slug=slug)
    if not profile.page_active:
        raise Http404

    user = profile.user

    # Resolve WhatsApp: prefer profile CTA, fall back to booking link
    whatsapp = profile.cta_whatsapp or ""
    if not whatsapp:
        bl = user.booking_links.filter(is_active=True).first()
        whatsapp = (bl.owner_whatsapp if bl else "") or ""

    # Pre-filled WhatsApp message
    business_name = profile.company_name or user.full_name or "your business"
    wa_text = f"Hi, I found your page on Kova and I'm interested in {business_name}. Can you help me?"
    wa_url = f"https://wa.me/{whatsapp}?text={quote(wa_text)}" if whatsapp else ""

    # Services: from key_offerings first, then active booking link
    services = list(profile.key_offerings or [])
    booking_link = user.booking_links.filter(is_active=True).first()
    if not services and booking_link:
        services = booking_link.services or []

    return render(request, "kova_page/page.html", {
        "profile": profile,
        "user": user,
        "whatsapp": whatsapp,
        "wa_url": wa_url,
        "services": services,
        "booking_link": booking_link,
        "page_title": profile.company_name or user.full_name or "Kova Page",
    })


@csrf_exempt
@require_POST
def page_contact(request, slug):
    """Contact form submission — creates a Lead for the business owner."""
    profile = get_object_or_404(UserProfile, page_slug=slug)
    if not profile.page_active:
        raise Http404

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    email = (request.POST.get("email") or "").strip()
    message = (request.POST.get("message") or "").strip()

    if not name or (not phone and not email):
        return JsonResponse({"error": "Name and phone or email are required."}, status=400)

    from apps.leads.models import Lead
    # email is optional; use a placeholder so unique_together doesn't crash on blank
    if not email:
        email = f"noemail_{phone}@kova.page"

    Lead.objects.update_or_create(
        user=profile.user,
        email=email,
        defaults={
            "name": name,
            "phone": phone,
            "source_type": Lead.Source.FORM_SUBMISSION,
            "source_platform": "kova_page",
            "notes": message,
            "metadata": {"page_slug": slug},
        },
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})

    return render(request, "kova_page/thankyou.html", {
        "profile": profile,
        "name": name,
    })
