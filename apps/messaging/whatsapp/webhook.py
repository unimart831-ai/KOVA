"""
WhatsApp Cloud API Webhook.

This endpoint receives ALL WhatsApp events from Meta:
1. Inbound messages (text, image, interactive replies, etc.)
2. Message status updates (sent → delivered → read → failed)
3. Template status changes (approved, rejected, paused)

Security:
- GET: Meta sends a verification challenge when you register the webhook.
  We verify the token matches our WHATSAPP_VERIFY_TOKEN.
- POST: Meta signs every payload with HMAC-SHA256 using the app secret.
  We verify the signature before processing.

Flow:
  Meta → POST /whatsapp/webhook/ → verify signature → parse event type →
  → inbound message: create/update conversation + message, trigger AI reply
  → status update: update message status (delivered/read/failed)
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from apps.core.platforms.models import SocialAccount
from apps.core.platforms.providers.registry import get_provider
from apps.messaging.whatsapp.models import (
    WhatsAppConversation,
    WhatsAppMessage,
)

logger = logging.getLogger(__name__)


@csrf_exempt
def whatsapp_webhook(request):
    """
    Main webhook endpoint for WhatsApp Cloud API.
    Handles both GET (verification) and POST (events).
    """
    if request.method == "GET":
        return _handle_verification(request)
    elif request.method == "POST":
        return _handle_event(request)
    return HttpResponse(status=405)


# ── Verification (GET) ───────────────────────────────────────────────────────

def _handle_verification(request):
    """
    Handle Meta's webhook verification challenge.

    When you register a webhook URL in Meta Developer Portal, Meta sends:
      GET /webhook/?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>

    We verify the token matches our WHATSAPP_VERIFY_TOKEN and echo back the challenge.
    """
    mode = request.GET.get("hub.mode", "")
    token = request.GET.get("hub.verify_token", "")
    challenge = request.GET.get("hub.challenge", "")

    verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")

    if mode == "subscribe" and token == verify_token:
        logger.info("WhatsApp webhook verified successfully")
        return HttpResponse(challenge, content_type="text/plain")

    logger.warning("WhatsApp webhook verification failed: mode=%s", mode)
    return HttpResponse("Forbidden", status=403)


# ── Event Processing (POST) ──────────────────────────────────────────────────

def _handle_event(request):
    """
    Process incoming webhook events from Meta.

    Payload structure:
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "id": "<WABA_ID>",
        "changes": [{
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "...", "display_phone_number": "..."},
            "messages": [...],        # Inbound messages
            "statuses": [...],        # Message status updates
            "contacts": [...]         # Sender info
          },
          "field": "messages"
        }]
      }]
    }
    """
    # Verify webhook signature (required in production)
    provider = get_provider("whatsapp")
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not settings.DEBUG and not signature:
        logger.warning("WhatsApp webhook missing X-Hub-Signature-256 in production")
        return HttpResponse("Missing signature", status=403)
    if provider:
        if not provider.verify_webhook_signature(request.body, signature):
            logger.warning("WhatsApp webhook signature verification failed")
            return HttpResponse("Invalid signature", status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponse("Invalid JSON", status=400)

    if body.get("object") != "whatsapp_business_account":
        return HttpResponse("ok", status=200)

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue

            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            if not phone_number_id:
                continue

            contacts = {c["wa_id"]: c for c in value.get("contacts", [])}
            messages = value.get("messages", [])
            statuses = value.get("statuses", [])

            # Kova master number — owner reply-to-act for daily brief (not customer inbox)
            master_phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
            if master_phone_id and phone_number_id == master_phone_id:
                for msg_data in messages:
                    try:
                        from apps.create.briefs.whatsapp_commands import handle_owner_whatsapp_message
                        handle_owner_whatsapp_message(msg_data, contacts)
                    except Exception:
                        logger.exception("Brief WhatsApp command handler failed")
                for status_data in statuses:
                    _process_status_update(status_data)
                continue

            # User-connected WhatsApp Business accounts (customer inbox)
            social_account = _find_social_account(phone_number_id)
            if not social_account:
                logger.warning("No SocialAccount found for phone_number_id=%s", phone_number_id)
                continue

            for msg_data in messages:
                _process_inbound_message(social_account, msg_data, contacts)

            for status_data in statuses:
                _process_status_update(status_data)

    # Always return 200 to Meta — they retry on non-200 and may throttle
    return HttpResponse("ok", status=200)


# ── Inbound Message Processing ───────────────────────────────────────────────

def _process_inbound_message(social_account, msg_data, contacts):
    """
    Process a single inbound message.

    1. Get or create the conversation thread
    2. Store the message
    3. Open/extend the 24-hour service window
    4. Mark message as read (blue checkmarks)
    5. Trigger AI auto-reply (async via Celery)
    """
    wa_id = msg_data.get("from", "")
    wamid = msg_data.get("id", "")
    msg_type = msg_data.get("type", "text")

    if not wa_id or not wamid:
        return

    # Get contact info
    contact_info = contacts.get(wa_id, {})
    contact_name = contact_info.get("profile", {}).get("name", "")

    # Get or create conversation
    conversation, created = WhatsAppConversation.objects.get_or_create(
        social_account=social_account,
        contact_wa_id=wa_id,
        defaults={
            "contact_phone": wa_id,
            "contact_name": contact_name,
            "status": WhatsAppConversation.Status.ACTIVE,
        },
    )

    # Update conversation
    if contact_name and not conversation.contact_name:
        conversation.contact_name = contact_name
    conversation.open_window()
    conversation.status = WhatsAppConversation.Status.ACTIVE
    conversation.save(update_fields=[
        "contact_name", "window_expires_at", "last_message_at", "status", "updated_at",
    ])

    # Auto-create a Lead when enabled in user settings (default off)
    if created:
        try:
            profile = getattr(social_account.user, "profile", None)
            if profile and profile.autopilot_auto_create_wa_leads:
                from apps.commerce.leads.bridges import create_lead_from_whatsapp_conversation
                create_lead_from_whatsapp_conversation(conversation)
        except Exception as e:
            logger.warning("Failed to auto-create lead from WhatsApp conversation: %s", e)

    # Extract message content based on type
    content, media_url, interactive_data = _extract_message_content(msg_data, msg_type)

    # Deduplicate (Meta sometimes sends duplicates)
    if WhatsAppMessage.objects.filter(wamid=wamid).exists():
        return

    # Create message record
    message = WhatsAppMessage.objects.create(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.INBOUND,
        message_type=_map_message_type(msg_type),
        content=content,
        media_url=media_url,
        interactive_data=interactive_data,
        wamid=wamid,
        status=WhatsAppMessage.MessageStatus.DELIVERED,
    )

    # Operations Autopilot — FAQ keyword auto-replies (before AI queue)
    try:
        from apps.messaging.whatsapp.autopilot import try_faq_auto_reply
        if try_faq_auto_reply(conversation, message):
            logger.info("WhatsApp FAQ autopilot handled message %s", wamid[:12])
            return
    except Exception as e:
        logger.warning("FAQ autopilot failed: %s", e)

    if created:
        try:
            from apps.messaging.whatsapp.services import enroll_conversation_in_onboarding_sequences
            enroll_conversation_in_onboarding_sequences(conversation)
        except Exception as e:
            logger.warning("Sequence enrollment failed: %s", e)

    # Mark as read (shows blue checkmarks to sender)
    provider = get_provider("whatsapp")
    if provider:
        provider.mark_as_read(social_account.access_token, wamid)

    # Trigger AI auto-reply (async)
    if conversation.ai_handling:
        try:
            from apps.messaging.whatsapp.tasks import handle_incoming_message
            handle_incoming_message.delay(str(message.id))
        except Exception as e:
            logger.error("Failed to queue AI reply task: %s", e)

    logger.info(
        "WhatsApp inbound: %s → %s (%s) [%s]",
        wa_id, social_account.username, msg_type, wamid[:12],
    )


def _extract_message_content(msg_data, msg_type):
    """Extract content, media_url, and interactive_data from a message payload."""
    content = ""
    media_url = ""
    interactive_data = {}

    if msg_type == "text":
        content = msg_data.get("text", {}).get("body", "")

    elif msg_type in ("image", "video", "audio", "document", "sticker"):
        media_info = msg_data.get(msg_type, {})
        media_url = media_info.get("link", "")  # May need to fetch via media ID
        content = media_info.get("caption", "")
        if not media_url and media_info.get("id"):
            # Store the media ID — we'll need to call GET /<media_id> to get the URL
            interactive_data["media_id"] = media_info["id"]
            interactive_data["mime_type"] = media_info.get("mime_type", "")

    elif msg_type == "location":
        loc = msg_data.get("location", {})
        content = f"📍 Location: {loc.get('name', '')} ({loc.get('latitude')}, {loc.get('longitude')})"
        interactive_data = loc

    elif msg_type == "contacts":
        contacts_list = msg_data.get("contacts", [])
        names = [c.get("name", {}).get("formatted_name", "") for c in contacts_list]
        content = f"📇 Shared contact(s): {', '.join(names)}"
        interactive_data = {"contacts": contacts_list}

    elif msg_type == "interactive":
        interactive = msg_data.get("interactive", {})
        inter_type = interactive.get("type", "")
        if inter_type == "button_reply":
            reply = interactive.get("button_reply", {})
            content = reply.get("title", "")
            interactive_data = {"type": "button_reply", **reply}
        elif inter_type == "list_reply":
            reply = interactive.get("list_reply", {})
            content = reply.get("title", "")
            interactive_data = {"type": "list_reply", **reply}

    elif msg_type == "order":
        order = msg_data.get("order", {})
        items = order.get("product_items", [])
        content = f"🛒 Order: {len(items)} item(s)"
        interactive_data = order

    elif msg_type == "reaction":
        reaction = msg_data.get("reaction", {})
        content = reaction.get("emoji", "")
        interactive_data = {
            "type": "reaction",
            "message_id": reaction.get("message_id", ""),
            "emoji": content,
        }

    return content, media_url, interactive_data


def _map_message_type(api_type):
    """Map WhatsApp API message type to our model's MessageType."""
    type_map = {
        "text": WhatsAppMessage.MessageType.TEXT,
        "image": WhatsAppMessage.MessageType.IMAGE,
        "video": WhatsAppMessage.MessageType.VIDEO,
        "audio": WhatsAppMessage.MessageType.AUDIO,
        "document": WhatsAppMessage.MessageType.DOCUMENT,
        "sticker": WhatsAppMessage.MessageType.STICKER,
        "location": WhatsAppMessage.MessageType.LOCATION,
        "contacts": WhatsAppMessage.MessageType.CONTACTS,
        "interactive": WhatsAppMessage.MessageType.INTERACTIVE,
        "order": WhatsAppMessage.MessageType.ORDER,
        "reaction": WhatsAppMessage.MessageType.REACTION,
    }
    return type_map.get(api_type, WhatsAppMessage.MessageType.TEXT)


# ── Status Update Processing ─────────────────────────────────────────────────

def _process_status_update(status_data):
    """
    Process a message status update.

    Meta sends: sent → delivered → read (or failed).
    We update the WhatsAppMessage record to track delivery lifecycle.
    """
    wamid = status_data.get("id", "")
    status = status_data.get("status", "")

    if not wamid:
        return

    status_map = {
        "sent": WhatsAppMessage.MessageStatus.SENT,
        "delivered": WhatsAppMessage.MessageStatus.DELIVERED,
        "read": WhatsAppMessage.MessageStatus.READ,
        "failed": WhatsAppMessage.MessageStatus.FAILED,
    }

    new_status = status_map.get(status)
    if not new_status:
        return

    try:
        message = WhatsAppMessage.objects.get(wamid=wamid)

        # Only advance status forward (don't go from 'read' back to 'delivered')
        status_order = {
            WhatsAppMessage.MessageStatus.PENDING: 0,
            WhatsAppMessage.MessageStatus.SENT: 1,
            WhatsAppMessage.MessageStatus.DELIVERED: 2,
            WhatsAppMessage.MessageStatus.READ: 3,
            WhatsAppMessage.MessageStatus.FAILED: 4,  # Failed can happen at any point
        }
        if (new_status != WhatsAppMessage.MessageStatus.FAILED
                and status_order.get(new_status, 0) <= status_order.get(message.status, 0)):
            return

        message.status = new_status
        message.status_updated_at = timezone.now()

        if status == "failed":
            errors = status_data.get("errors", [])
            if errors:
                message.error_code = errors[0].get("code")
                message.error_message = errors[0].get("title", "")

        message.save(update_fields=["status", "status_updated_at", "error_code", "error_message"])

        try:
            from apps.messaging.whatsapp.services import update_broadcast_delivery_stats
            update_broadcast_delivery_stats(message, new_status)
        except Exception:
            pass

    except WhatsAppMessage.DoesNotExist:
        # Status update for a message we don't have (e.g., sent before Kova was connected)
        pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_social_account(phone_number_id):
    """Find the SocialAccount that matches this WhatsApp phone number ID."""
    try:
        return SocialAccount.objects.get(
            platform="whatsapp",
            is_active=True,
            metadata__phone_number_id=phone_number_id,
        )
    except SocialAccount.DoesNotExist:
        # Fallback: check platform_user_id
        try:
            return SocialAccount.objects.get(
                platform="whatsapp",
                is_active=True,
                platform_user_id=phone_number_id,
            )
        except SocialAccount.DoesNotExist:
            return None
    except SocialAccount.MultipleObjectsReturned:
        return SocialAccount.objects.filter(
            platform="whatsapp",
            is_active=True,
            platform_user_id=phone_number_id,
        ).first()
