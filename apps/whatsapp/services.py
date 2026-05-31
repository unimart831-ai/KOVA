"""
Unified WhatsApp outbound messaging layer.

Callers (nurture, bookings, reviews, broadcasts, commerce) use these helpers
instead of talking to the provider directly. Handles account resolution,
24-hour window vs template fallback, Meta component formatting, and logging.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class WhatsAppSendError(Exception):
    """Outbound send failed (no account, API error, or policy block)."""


def normalize_wa_id(phone: str) -> str:
    """Strip +, spaces, and leading zeros for Kenya-style numbers."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9:
        digits = "254" + digits
    return digits


def resolve_social_account(
    user=None,
    phone_number_id: str | None = None,
):
    """Resolve the active WhatsApp SocialAccount for a user or phone_number_id."""
    from apps.platforms.models import SocialAccount

    if phone_number_id:
        try:
            return SocialAccount.objects.get(
                platform="whatsapp",
                is_active=True,
                metadata__phone_number_id=phone_number_id,
            )
        except SocialAccount.DoesNotExist:
            try:
                return SocialAccount.objects.get(
                    platform="whatsapp",
                    is_active=True,
                    platform_user_id=phone_number_id,
                )
            except SocialAccount.DoesNotExist:
                return None

    if user is None:
        return None

    return (
        SocialAccount.objects.filter(
            user=user, platform="whatsapp", is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )


def get_or_create_conversation(
    social_account,
    contact_wa_id: str,
    contact_name: str = "",
):
    from apps.whatsapp.models import WhatsAppConversation

    wa_id = normalize_wa_id(contact_wa_id) or contact_wa_id
    conversation, created = WhatsAppConversation.objects.get_or_create(
        social_account=social_account,
        contact_wa_id=wa_id,
        defaults={
            "contact_phone": wa_id,
            "contact_name": contact_name,
            "status": WhatsAppConversation.Status.ACTIVE,
        },
    )
    return conversation, created


def variables_to_components(variables: Any) -> list[dict] | None:
    """
    Convert template variable payloads to Meta Cloud API components.

    Accepts:
      - list of strings -> body parameters in order
      - dict {1: "val", 2: "val"} or {"1": "val"} -> body parameters
      - list of component dicts (passthrough)
      - dict with "components" key
    """
    if not variables:
        return None

    if isinstance(variables, list):
        if variables and isinstance(variables[0], dict) and "type" in variables[0]:
            return variables
        params = [{"type": "text", "text": str(v)} for v in variables]
        return [{"type": "body", "parameters": params}] if params else None

    if isinstance(variables, dict):
        if "components" in variables:
            return variables["components"]
        numeric_keys = []
        for key in variables:
            try:
                numeric_keys.append((int(key), variables[key]))
            except (TypeError, ValueError):
                continue
        if numeric_keys:
            numeric_keys.sort(key=lambda x: x[0])
            params = [{"type": "text", "text": str(v)} for _, v in numeric_keys]
            return [{"type": "body", "parameters": params}] if params else None
        # Named fields (bookings, etc.) — stable alphabetical order
        if variables:
            params = [
                {"type": "text", "text": str(variables[k])}
                for k in sorted(variables.keys())
            ]
            return [{"type": "body", "parameters": params}]

    return None


def build_meta_template_components(template) -> list[dict]:
    """Build Meta message_templates components from a WhatsAppTemplate row."""
    components: list[dict] = []

    header_type = (template.header_type or "none").lower()
    if header_type == "text" and template.header_text:
        components.append({
            "type": "HEADER",
            "format": "TEXT",
            "text": template.header_text[:60],
        })
    elif header_type in ("image", "video", "document") and template.header_media_url:
        components.append({
            "type": "HEADER",
            "format": header_type.upper(),
            "example": {"header_handle": [template.header_media_url]},
        })

    components.append({"type": "BODY", "text": template.body_text})

    if template.footer_text:
        components.append({"type": "FOOTER", "text": template.footer_text[:60]})

    if template.buttons:
        meta_buttons = []
        for btn in template.buttons[:3]:
            btn_type = (btn.get("type") or "QUICK_REPLY").upper()
            if btn_type == "URL":
                meta_buttons.append({
                    "type": "URL",
                    "text": btn.get("text", "Visit")[:25],
                    "url": btn.get("url", ""),
                })
            elif btn_type == "PHONE_NUMBER":
                meta_buttons.append({
                    "type": "PHONE_NUMBER",
                    "text": btn.get("text", "Call")[:25],
                    "phone_number": btn.get("phone_number", ""),
                })
            else:
                meta_buttons.append({
                    "type": "QUICK_REPLY",
                    "text": btn.get("text", "Reply")[:25],
                })
        if meta_buttons:
            components.append({"type": "BUTTONS", "buttons": meta_buttons})

    return components


def _get_provider():
    from apps.platforms.providers.registry import get_provider
    provider = get_provider("whatsapp")
    if not provider:
        raise WhatsAppSendError("WhatsApp provider is not configured")
    return provider


def _record_outbound(
    conversation,
    *,
    body: str,
    message_type: str,
    wamid: str = "",
    status: str = "sent",
    template=None,
    is_ai: bool = False,
    confidence: float | None = None,
    extra: dict | None = None,
):
    from apps.whatsapp.models import WhatsAppMessage

    msg = WhatsAppMessage.objects.create(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        message_type=getattr(WhatsAppMessage.MessageType, message_type.upper(), message_type),
        content=body,
        wamid=wamid,
        status=status,
        template=template,
        is_ai_generated=is_ai,
        confidence_score=confidence,
        interactive_data=extra or {},
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at", "updated_at"])
    return msg


def send_text_message(
    to: str,
    body: str,
    *,
    user=None,
    social_account=None,
    preview_url: bool = False,
    force_template: bool = False,
    is_ai_generated: bool = False,
    confidence_score: float | None = None,
) -> dict:
    """
    Send a free-form text message (within 24h window) or fall back to a utility template.

    Returns dict with success, wamid, conversation_id.
    """
    social_account = social_account or resolve_social_account(user=user)
    if not social_account:
        raise WhatsAppSendError("No active WhatsApp account for this user")

    wa_id = normalize_wa_id(to) or to
    conversation, _ = get_or_create_conversation(social_account, wa_id)
    provider = _get_provider()

    use_template = force_template or not conversation.is_window_open
    if use_template:
        # Outside service window — caller should use send_template_message explicitly.
        raise WhatsAppSendError(
            "24-hour window closed; use send_template_message with an approved template"
        )

    result = provider.send_text_message(
        access_token=social_account.access_token,
        to=wa_id,
        body=body,
        preview_url=preview_url,
        phone_number_id=social_account.metadata.get("phone_number_id"),
    )

    if not result.get("success"):
        raise WhatsAppSendError(result.get("error", "Send failed"))

    _record_outbound(
        conversation,
        body=body,
        message_type="text",
        wamid=result.get("wamid", ""),
        status="sent",
        is_ai=is_ai_generated,
        confidence=confidence_score,
    )
    return {
        "success": True,
        "wamid": result.get("wamid"),
        "conversation_id": str(conversation.pk),
    }


def send_template_message(
    to: str,
    template_name: str,
    *,
    variables: Any = None,
    language: str | None = None,
    user=None,
    social_account=None,
    template_obj=None,
    broadcast_id: str | None = None,
) -> dict:
    """Send an approved Meta template message."""
    social_account = social_account or resolve_social_account(user=user)
    if not social_account:
        raise WhatsAppSendError("No active WhatsApp account for this user")

    from apps.whatsapp.models import WhatsAppTemplate

    wa_id = normalize_wa_id(to) or to
    conversation, _ = get_or_create_conversation(social_account, wa_id)
    provider = _get_provider()

    if template_obj is None:
        template_obj = WhatsAppTemplate.objects.filter(
            social_account=social_account,
            name=template_name,
            status=WhatsAppTemplate.TemplateStatus.APPROVED,
        ).first()
        if not template_obj:
            template_obj = WhatsAppTemplate.objects.filter(
                social_account=social_account,
                name=template_name,
            ).first()

    lang = language or (template_obj.language if template_obj else "en")
    components = variables_to_components(variables)
    body_preview = template_obj.body_text if template_obj else template_name

    result = provider.send_template_message(
        access_token=social_account.access_token,
        to=wa_id,
        template_name=template_name,
        language_code=lang,
        components=components,
        phone_number_id=social_account.metadata.get("phone_number_id"),
    )

    if not result.get("success"):
        raise WhatsAppSendError(result.get("error", "Template send failed"))

    extra = {}
    if broadcast_id:
        extra["broadcast_id"] = broadcast_id

    _record_outbound(
        conversation,
        body=body_preview,
        message_type="template",
        wamid=result.get("wamid", ""),
        status="sent",
        template=template_obj,
        extra=extra,
    )
    return {
        "success": True,
        "wamid": result.get("wamid"),
        "conversation_id": str(conversation.pk),
    }


def submit_template_to_meta(template) -> dict:
    """Submit a draft WhatsAppTemplate to Meta for approval."""
    from apps.whatsapp.models import WhatsAppTemplate

    social_account = template.social_account
    waba_id = social_account.metadata.get("waba_id", "")
    if not waba_id:
        raise WhatsAppSendError("WhatsApp Business Account ID (waba_id) not configured")

    provider = _get_provider()
    components = build_meta_template_components(template)
    result = provider.create_template(
        access_token=social_account.access_token,
        waba_id=waba_id,
        name=template.name,
        category=template.category,
        language=template.language,
        components=components,
    )

    if result.get("success"):
        template.meta_template_id = result.get("template_id", "")
        template.status = WhatsAppTemplate.TemplateStatus.SUBMITTED
        template.rejection_reason = ""
        template.save(update_fields=["meta_template_id", "status", "rejection_reason", "updated_at"])
    else:
        template.rejection_reason = result.get("error", "Submission failed")[:500]
        template.save(update_fields=["rejection_reason", "updated_at"])
        raise WhatsAppSendError(template.rejection_reason)

    return result


def sync_templates_from_meta(social_account) -> int:
    """Pull template statuses from Meta and update local WhatsAppTemplate rows."""
    from apps.whatsapp.models import WhatsAppTemplate

    waba_id = social_account.metadata.get("waba_id", "")
    if not waba_id:
        return 0

    provider = _get_provider()
    remote = provider.get_templates(
        access_token=social_account.access_token,
        waba_id=waba_id,
    )

    status_map = {
        "APPROVED": WhatsAppTemplate.TemplateStatus.APPROVED,
        "REJECTED": WhatsAppTemplate.TemplateStatus.REJECTED,
        "PENDING": WhatsAppTemplate.TemplateStatus.SUBMITTED,
        "PAUSED": WhatsAppTemplate.TemplateStatus.PAUSED,
    }
    updated = 0

    for item in remote:
        name = item.get("name", "")
        language = item.get("language", "en")
        meta_status = item.get("status", "")
        local = WhatsAppTemplate.objects.filter(
            social_account=social_account,
            name=name,
            language=language,
        ).first()
        if not local:
            body = ""
            for comp in item.get("components", []):
                if comp.get("type") == "BODY":
                    body = comp.get("text", "")
            WhatsAppTemplate.objects.create(
                social_account=social_account,
                name=name,
                category=(item.get("category") or "marketing").lower(),
                language=language,
                body_text=body or name,
                meta_template_id=item.get("id", ""),
                status=status_map.get(meta_status, WhatsAppTemplate.TemplateStatus.DRAFT),
            )
            updated += 1
            continue

        new_status = status_map.get(meta_status)
        fields = []
        if new_status and local.status != new_status:
            local.status = new_status
            fields.append("status")
        if item.get("id") and local.meta_template_id != item.get("id"):
            local.meta_template_id = item.get("id", "")
            fields.append("meta_template_id")
        if fields:
            fields.append("updated_at")
            local.save(update_fields=fields)
            updated += 1

    return updated


def enroll_conversation_in_onboarding_sequences(conversation):
    """Enroll a new conversation in active onboarding drip sequences."""
    from datetime import timedelta

    from apps.whatsapp.models import (
        BroadcastSequence,
        BroadcastSequenceStep,
        SequenceEnrollment,
    )

    sequences = BroadcastSequence.objects.filter(
        social_account=conversation.social_account,
        status=BroadcastSequence.SequenceStatus.ACTIVE,
        sequence_type=BroadcastSequence.SequenceType.ONBOARDING,
    )

    enrolled = 0
    now = timezone.now()

    for sequence in sequences:
        if SequenceEnrollment.objects.filter(
            sequence=sequence,
            conversation=conversation,
            status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
        ).exists():
            continue

        first_step = BroadcastSequenceStep.objects.filter(
            sequence=sequence, order=1,
        ).first()
        next_send = now + timedelta(hours=first_step.delay_hours if first_step else 0)

        SequenceEnrollment.objects.create(
            sequence=sequence,
            conversation=conversation,
            current_step=0,
            next_send_at=next_send,
            status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
        )
        sequence.enrolled_count = sequence.enrollments.filter(
            status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
        ).count()
        sequence.save(update_fields=["enrolled_count", "updated_at"])
        enrolled += 1

    return enrolled


def update_broadcast_delivery_stats(message, new_status: str):
    """Increment broadcast delivered/read counts when webhook status arrives."""
    from apps.whatsapp.models import WhatsAppBroadcast, WhatsAppMessage

    broadcast_id = (message.interactive_data or {}).get("broadcast_id")
    if not broadcast_id:
        return

    try:
        broadcast = WhatsAppBroadcast.objects.get(pk=broadcast_id)
    except WhatsAppBroadcast.DoesNotExist:
        return

    if new_status == WhatsAppMessage.MessageStatus.DELIVERED:
        WhatsAppBroadcast.objects.filter(pk=broadcast.pk).update(
            delivered_count=broadcast.delivered_count + 1,
        )
    elif new_status == WhatsAppMessage.MessageStatus.READ:
        WhatsAppBroadcast.objects.filter(pk=broadcast.pk).update(
            read_count=broadcast.read_count + 1,
        )


def send_commerce_payment_receipt(commerce_payment, phone: str, receipt: str, amount) -> bool:
    """Send M-Pesa payment confirmation via WhatsApp when possible."""
    user = commerce_payment.user
    product = commerce_payment.product
    product_name = product.name if product else "your order"
    amount_str = f"KES {amount:,.0f}" if hasattr(amount, "__float__") else str(amount)

    message = (
        f"✅ Payment received!\n\n"
        f"Amount: {amount_str}\n"
        f"Receipt: {receipt}\n"
        f"Item: {product_name}\n\n"
        f"Asante for your order! We'll confirm delivery details shortly."
    )

    try:
        send_text_message(to=phone, body=message, user=user)
        return True
    except WhatsAppSendError:
        # Window may be closed — try utility template if one exists
        try:
            send_template_message(
                to=phone,
                template_name="order_confirmation",
                variables=[amount_str, receipt, product_name],
                user=user,
            )
            return True
        except WhatsAppSendError as e:
            logger.info("Commerce WhatsApp receipt skipped: %s", e)
            return False
