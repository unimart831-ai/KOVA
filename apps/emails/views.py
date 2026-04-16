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

    # Find the log entry — try provider_message_id first, then our custom
    # Message-ID header (log UUID), then fallback to to_email + recent time
    log = None
    try:
        log = EmailLog.objects.get(provider_message_id=email_id)
    except EmailLog.DoesNotExist:
        pass

    if not log:
        # Try matching by our log UUID embedded in the Message-ID header
        # Resend echoes back the custom Message-ID in some webhook payloads
        headers = data.get("headers", {})
        message_id = headers.get("message-id", "")
        if message_id:
            # Extract UUID from "<uuid@domain>" format
            log_uuid = message_id.strip("<>").split("@")[0]
            try:
                log = EmailLog.objects.get(pk=log_uuid)
            except (EmailLog.DoesNotExist, ValueError):
                pass

    if not log:
        # Fallback: match by recipient + recent sent time
        to_email = ""
        to_list = data.get("to", [])
        if isinstance(to_list, list) and to_list:
            to_email = to_list[0] if isinstance(to_list[0], str) else ""
        elif isinstance(to_list, str):
            to_email = to_list

        if to_email:
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(hours=48)
            log = (
                EmailLog.objects.filter(
                    to_email=to_email,
                    status__in=[EmailLog.Status.SENT, EmailLog.Status.DELIVERED],
                    sent_at__gte=cutoff,
                )
                .order_by("-sent_at")
                .first()
            )

    if not log:
        logger.debug("Webhook for unknown email_id: %s", email_id)
        return HttpResponse(status=200)

    # Store the Resend message ID for future webhook correlation
    if email_id and not log.provider_message_id:
        log.provider_message_id = email_id
        log.save(update_fields=["provider_message_id"])

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

        # Auto-update subscriber bounce count
        from apps.emails.models import EmailSubscriber
        if log.user:
            try:
                sub = EmailSubscriber.objects.get(user=log.user, email=log.to_email)
                sub.record_bounce()
            except EmailSubscriber.DoesNotExist:
                pass

    elif event_type == "email.complained":
        log.status = EmailLog.Status.SPAM
        log.save(update_fields=["status"])

        # Auto-mark subscriber as complained
        from apps.emails.models import EmailSubscriber
        if log.user:
            EmailSubscriber.objects.filter(
                user=log.user, email=log.to_email,
            ).exclude(
                status=EmailSubscriber.Status.COMPLAINED,
            ).update(status=EmailSubscriber.Status.COMPLAINED)

    logger.info("Resend webhook: %s for email %s", event_type, email_id)
    return HttpResponse(status=200)


# ─── Public one-click unsubscribe (no login required) ────────────────────


@csrf_exempt
@ratelimit(key="ip", rate="30/m", block=True)
def unsubscribe(request, token):
    """
    One-click unsubscribe endpoint. Handles both GET (link click) and
    POST (List-Unsubscribe header in email clients like Gmail).

    CAN-SPAM / GDPR compliant: no login, no confirmation page required.
    """
    from apps.emails.models import EmailSubscriber

    try:
        subscriber = EmailSubscriber.objects.get(unsubscribe_token=token)
    except EmailSubscriber.DoesNotExist:
        # Show a generic page — don't reveal whether token exists
        return _unsubscribe_response(success=False)

    if subscriber.status != EmailSubscriber.Status.UNSUBSCRIBED:
        subscriber.status = EmailSubscriber.Status.UNSUBSCRIBED
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save(update_fields=["status", "unsubscribed_at"])
        logger.info("Subscriber unsubscribed: %s (owner: %s)", subscriber.email, subscriber.user_id)

    # POST from email client List-Unsubscribe-Post header
    if request.method == "POST":
        return HttpResponse(status=200)

    return _unsubscribe_response(success=True, email=subscriber.email)


def _unsubscribe_response(success=True, email=""):
    """Return a simple HTML unsubscribe confirmation page."""
    if success:
        title = "Unsubscribed"
        message = f"<strong>{email}</strong> has been unsubscribed. You won't receive marketing emails from this sender anymore."
    else:
        title = "Invalid Link"
        message = "This unsubscribe link is invalid or has already expired."

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Kova Agent</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
    .card {{ background: #fff; border-radius: 12px; padding: 40px; max-width: 420px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
    h1 {{ font-size: 24px; color: #111827; margin: 0 0 12px; }}
    p {{ font-size: 14px; color: #6b7280; line-height: 1.6; margin: 0; }}
    a {{ color: #7c3aed; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <p>{message}</p>
    <p style="margin-top: 20px;"><a href="https://kovaagent.com">← Back to Kova Agent</a></p>
  </div>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html")
