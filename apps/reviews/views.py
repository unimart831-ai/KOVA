"""Views for the review request loop (Phase 3 W9).

User-authenticated:
  reviews_list      GET  /reviews/                 list ReviewRequests
  review_detail     GET  /reviews/<id>/            single detail

Public:
  capture_response  POST /reviews/<id>/respond/    inbound webhook + form
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.reviews.models import ReviewRequest
from apps.reviews.services import process_response


@login_required
def reviews_list(request):
    all_qs = ReviewRequest.objects.filter(user=request.user)
    qs = all_qs.order_by("-created_at")[:100]
    pending = all_qs.filter(status=ReviewRequest.Status.PENDING).count()
    responded = all_qs.filter(status=ReviewRequest.Status.RESPONDED).count()
    return render(request, "reviews/list.html", {
        "reviews": qs,
        "pending_count": pending,
        "responded_count": responded,
        "page_title": "Reviews",
    })


@login_required
def review_detail(request, pk):
    req = get_object_or_404(ReviewRequest, pk=pk, user=request.user)
    return render(request, "reviews/detail.html", {
        "req": req,
        "page_title": str(req),
    })


@csrf_exempt
@require_POST
def capture_response(request, pk):
    """Public POST endpoint. Used by:
      * WhatsApp inbound webhook (the Engage inbound pipeline can forward
        replies-to-review-requests here)
      * A bare HTML form fallback when the customer follows an email link

    Body: `text` — the response text.
    """
    req = get_object_or_404(ReviewRequest, pk=pk)
    if req.status == ReviewRequest.Status.RESPONDED:
        return JsonResponse({"ok": True, "already": True})

    text = (request.POST.get("text") or "").strip()[:2000]
    if not text:
        return HttpResponseBadRequest("text is required")

    process_response(req, text)
    return JsonResponse({
        "ok": True,
        "sentiment": req.sentiment,
        "sentiment_score": req.sentiment_score,
    })
