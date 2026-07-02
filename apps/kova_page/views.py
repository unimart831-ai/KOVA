"""
Kova Link Page — public conversion page per business.

Public:
  page_view      GET  /p/<slug>/         — anyone with the link
  page_ask       POST /p/<slug>/ask/     — AI Salesperson (grounded)
  page_contact   POST /p/<slug>/contact/ — contact form → Lead
"""
from __future__ import annotations

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.models import UserProfile


@require_GET
def page_view(request, slug):
    profile = get_object_or_404(UserProfile, page_slug=slug)
    if not profile.page_active:
        raise Http404

    from apps.kova_page.hub import build_hub_context

    context = build_hub_context(profile, profile.user)
    return render(request, "kova_page/page.html", context)


@csrf_exempt
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
@require_POST
def page_ask(request, slug):
    """AI Salesperson — answer a visitor's question grounded in the business."""
    profile = get_object_or_404(UserProfile, page_slug=slug)
    if not profile.page_active:
        raise Http404

    question = (request.POST.get("q") or request.POST.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "Ask a question first."}, status=400)

    from apps.kova_page.salesperson import answer_customer_question

    result = answer_customer_question(profile, profile.user, question)
    return JsonResponse(result)



@csrf_exempt
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
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
