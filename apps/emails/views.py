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

from apps.emails.models import EmailLog

logger = logging.getLogger(__name__)


@csrf_exempt
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
