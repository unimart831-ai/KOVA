"""
Views for the emails app — webhook handler for Resend delivery events.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.emails.models import EmailLog

logger = logging.getLogger(__name__)


def _verify_resend_signature(request) -> bool:
    """
    Verify Resend webhook signature using svix headers.

    Resend uses Svix to deliver webhooks. The signature is in the
    'svix-signature' header. We verify using HMAC-SHA256 with the
    webhook signing secret.

    Returns True if signature is valid OR if no secret is configured
    (dev/testing mode with a warning).
    """
    signing_secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
    if not signing_secret:
        logger.warning(
            "RESEND_WEBHOOK_SECRET not configured — accepting webhook without "
            "signature verification. Set this in production!"
        )
        return True

    # Resend/Svix sends these headers
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    if not all([svix_id, svix_timestamp, svix_signature]):
        logger.warning("Resend webhook missing svix headers")
        return False

    # Svix secret starts with "whsec_" — strip the prefix and base64 decode
    import base64

    if signing_secret.startswith("whsec_"):
        signing_secret = signing_secret[6:]

    try:
        secret_bytes = base64.b64decode(signing_secret)
    except Exception:
        logger.error("Failed to decode RESEND_WEBHOOK_SECRET — check format")
        return False

    # Build the signed content: "{msg_id}.{timestamp}.{body}"
    body = request.body.decode("utf-8")
    signed_content = f"{svix_id}.{svix_timestamp}.{body}"

    # Compute expected signature
    expected = hmac.new(
        secret_bytes,
        signed_content.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.b64encode(expected).decode("utf-8")

    # svix-signature can contain multiple signatures separated by spaces
    # Each is "v1,<base64>" — check if any match
    for sig in svix_signature.split(" "):
        parts = sig.split(",", 1)
        if len(parts) != 2:
            continue
        version, sig_b64 = parts
        if version != "v1":
            continue
        if hmac.compare_digest(expected_b64, sig_b64):
            return True

    logger.warning("Resend webhook signature verification failed")
    return False


@csrf_exempt
@ratelimit(key="ip", rate="60/m", block=True)
@require_POST
def resend_webhook(request):
    """
    Handle Resend delivery webhooks.

    Resend sends POST requests with event data for:
    - email.sent
    - email.delivered
    - email.opened
    - email.clicked
    - email.bounced
    - email.complained
    """
    # ── Verify webhook signature ─────────────────────────────────────
    if not _verify_resend_signature(request):
        logger.warning("Rejected Resend webhook — invalid signature")
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event_type = payload.get("type", "")
    data = payload.get("data", {})
    email_id = data.get("email_id", "")

    if not email_id:
        return HttpResponse(status=200)  # Acknowledge but ignore

    # Find the log entry by provider message ID
    try:
        log = EmailLog.objects.get(provider_message_id=email_id)
    except EmailLog.DoesNotExist:
        # Could be from before we started logging, or different system
        logger.debug("Webhook for unknown email_id: %s", email_id)
        return HttpResponse(status=200)

    now = timezone.now()

    if event_type == "email.delivered":
        log.status = EmailLog.Status.DELIVERED
        log.delivered_at = now
        log.save(update_fields=["status", "delivered_at"])

    elif event_type == "email.opened":
        if log.status != EmailLog.Status.CLICKED:  # Don't downgrade from clicked
            log.status = EmailLog.Status.OPENED
        log.opened_at = log.opened_at or now  # Keep first open time
        log.save(update_fields=["status", "opened_at"])

    elif event_type == "email.clicked":
        log.status = EmailLog.Status.CLICKED
        log.clicked_at = log.clicked_at or now
        log.save(update_fields=["status", "clicked_at"])

    elif event_type == "email.bounced":
        log.status = EmailLog.Status.BOUNCED
        log.failed_at = now
        log.error_message = data.get("bounce", {}).get("message", "Bounced")
        log.save(update_fields=["status", "failed_at", "error_message"])

    elif event_type == "email.complained":
        log.status = EmailLog.Status.SPAM
        log.save(update_fields=["status"])

    logger.info("Resend webhook: %s for email %s", event_type, email_id)
    return HttpResponse(status=200)
