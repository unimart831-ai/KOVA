"""Public instructions and Meta data-deletion callback endpoints."""

import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.platforms.facebook_data_deletion import (
    SignedRequestError,
    delete_facebook_user_data,
    get_deletion_status,
    make_confirmation_code,
    parse_signed_request,
    status_page_url,
    store_deletion_status,
)

logger = logging.getLogger(__name__)


def facebook_data_deletion_instructions(request):
    """Public page for Meta App Dashboard → Data deletion instructions URL."""
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    return render(
        request,
        "pages/facebook_data_deletion.html",
        {
            "site_url": site_url,
            "support_email": "support@kovaagent.com",
            "privacy_email": "privacy@kovaagent.com",
        },
    )


def facebook_data_deletion_status(request, confirmation_code: str):
    """Status page linked from Meta callback JSON (confirmation_code)."""
    record = get_deletion_status(confirmation_code)
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    return render(
        request,
        "pages/facebook_data_deletion_status.html",
        {
            "site_url": site_url,
            "confirmation_code": confirmation_code,
            "record": record,
            "found": record is not None,
        },
    )


@csrf_exempt
@require_POST
def facebook_data_deletion_callback(request):
    """
    Meta Data Deletion Callback URL.

    POST body: signed_request=<payload> (application/x-www-form-urlencoded).
    Returns JSON: { "url": "<status>", "confirmation_code": "<code>" }.
    """
    signed_request = request.POST.get("signed_request", "").strip()
    app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "") or ""

    if not app_secret:
        logger.error("Facebook data deletion callback: FACEBOOK_APP_SECRET not configured")
        return JsonResponse({"error": "not_configured"}, status=503)

    try:
        payload = parse_signed_request(signed_request, app_secret)
    except SignedRequestError as exc:
        logger.warning("Facebook data deletion: invalid signed_request: %s", exc)
        return JsonResponse({"error": "invalid_signed_request"}, status=400)

    facebook_user_id = str(payload.get("user_id") or "").strip()
    if not facebook_user_id:
        return JsonResponse({"error": "missing_user_id"}, status=400)

    confirmation_code = make_confirmation_code()
    counts = delete_facebook_user_data(facebook_user_id)
    store_deletion_status(
        confirmation_code,
        facebook_user_id=facebook_user_id,
        counts=counts,
    )

    return JsonResponse(
        {
            "url": status_page_url(confirmation_code),
            "confirmation_code": confirmation_code,
        }
    )


@require_GET
def facebook_data_deletion_callback_probe(request):
    """Allow health checks; Meta only POSTs signed_request."""
    return HttpResponse(
        "Kova Meta data deletion callback — POST signed_request only.",
        content_type="text/plain",
    )
