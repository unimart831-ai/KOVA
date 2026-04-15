"""
WhatsApp Celery Tasks — AI Auto-Reply Engine.

This is the brain of WhatsApp Intelligence. When a customer messages,
the webhook saves the message and fires handle_incoming_message() which:

1. Detects the customer's language (English, Swahili, Sheng)
2. Loads conversation history for context
3. Loads the brand's voice, offerings, and restrictions
4. Generates an AI reply using the Engage Agent's LLM
5. Routes based on confidence:
   - High (>0.8): Send automatically
   - Medium (0.5-0.8): Save draft, flag for review
   - Low (<0.5): Escalate to human, don't auto-reply
6. Sends the reply via the WhatsApp Cloud API
"""

import json
import logging

from celery import shared_task
from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json

logger = logging.getLogger(__name__)


# ─── Confidence thresholds ───────────────────────────────────────────────────
HIGH_CONFIDENCE = 0.8   # Auto-send immediately
MEDIUM_CONFIDENCE = 0.5  # Draft + flag for human review
# Below MEDIUM_CONFIDENCE = escalate to human


@shared_task(name="whatsapp.handle_incoming_message", bind=True, max_retries=2)
def handle_incoming_message(self, message_id: str):
    """
    Process an incoming WhatsApp message and generate an AI reply.

    Called async by the webhook after saving the inbound message.
    This is the core AI auto-reply pipeline.
    """
    from apps.whatsapp.models import WhatsAppConversation, WhatsAppMessage
    from apps.platforms.providers.registry import get_provider

    try:
        message = WhatsAppMessage.objects.select_related(
            "conversation", "conversation__social_account",
            "conversation__social_account__user",
        ).get(id=message_id)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("WhatsApp message %s not found", message_id)
        return

    conversation = message.conversation
    social_account = conversation.social_account
    user = social_account.user

    # Skip if AI handling is disabled for this conversation
    if not conversation.ai_handling:
        logger.info("AI handling disabled for conversation %s", conversation.id)
        return

    # Skip reactions and status messages — no reply needed
    if message.message_type in ("reaction",):
        return

    # Load brand context
    profile = getattr(user, "profile", None)
    if not profile:
        logger.warning("No profile for user %s — skipping AI reply", user.email)
        return

    # Get conversation history (last 20 messages for context)
    recent_messages = WhatsAppMessage.objects.filter(
        conversation=conversation,
    ).order_by("-created_at")[:20]
    recent_messages = list(reversed(recent_messages))

    # Detect language from the incoming message
    detected_language = _detect_language(message.content)
    if conversation.language == WhatsAppConversation.Language.UNKNOWN and detected_language:
        conversation.language = detected_language
        conversation.save(update_fields=["language", "updated_at"])

    # Build the AI prompt
    system_prompt = _build_system_prompt(profile, conversation)
    user_prompt = _build_conversation_prompt(recent_messages, message, conversation)

    # Generate AI reply
    model = get_model_for_task("engage")
    response = generate(
        prompt=user_prompt,
        system=system_prompt,
        model=model,
        temperature=0.7,
        max_tokens=1024,
        json_mode=True,
    )

    if not response.content:
        logger.warning("Empty LLM response for WhatsApp message %s", message_id)
        return

    # Parse the AI response
    parsed = parse_llm_json(response.content)
    if not parsed:
        logger.warning("Failed to parse LLM JSON for WhatsApp message %s", message_id)
        return

    reply_text = parsed.get("reply", "").strip()
    confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.5))))
    reasoning = parsed.get("reasoning", "")
    suggested_action = parsed.get("action", "reply")  # reply | escalate | no_reply

    if not reply_text or suggested_action == "no_reply":
        logger.info("AI chose not to reply to message %s (action=%s)", message_id, suggested_action)
        return

    # Route based on confidence
    if suggested_action == "escalate" or confidence < MEDIUM_CONFIDENCE:
        # LOW confidence: escalate to human
        _escalate_conversation(conversation, message, reply_text, confidence, reasoning)
        return

    # Create the outbound message record
    outbound = WhatsAppMessage.objects.create(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        message_type=WhatsAppMessage.MessageType.TEXT,
        content=reply_text,
        is_ai_generated=True,
        confidence_score=confidence,
        status=WhatsAppMessage.MessageStatus.PENDING,
    )

    if confidence >= HIGH_CONFIDENCE:
        # HIGH confidence: auto-send immediately
        provider = get_provider("whatsapp")
        if not provider:
            logger.error("WhatsApp provider not available")
            return

        result = provider.send_text_message(
            access_token=social_account.access_token,
            to=conversation.contact_wa_id,
            body=reply_text,
        )

        if result.get("success"):
            outbound.wamid = result.get("wamid", "")
            outbound.status = WhatsAppMessage.MessageStatus.SENT
            outbound.save(update_fields=["wamid", "status"])
            # Update conversation
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at", "updated_at"])
            logger.info(
                "WhatsApp AI auto-reply sent (confidence=%.2f) to %s",
                confidence, conversation.contact_wa_id,
            )
        else:
            outbound.status = WhatsAppMessage.MessageStatus.FAILED
            outbound.error_message = result.get("error", "Unknown error")
            outbound.save(update_fields=["status", "error_message"])
            logger.error("WhatsApp AI reply send failed: %s", result.get("error"))
    else:
        # MEDIUM confidence: save as draft for human review
        logger.info(
            "WhatsApp AI draft saved (confidence=%.2f) for review — conversation %s",
            confidence, conversation.id,
        )


def _escalate_conversation(conversation, trigger_message, draft_reply, confidence, reasoning):
    """Escalate a conversation to human handling."""
    conversation.ai_handling = False
    conversation.status = conversation.Status.ESCALATED
    context = conversation.context or {}
    context["escalation"] = {
        "reason": reasoning,
        "confidence": confidence,
        "trigger_message": trigger_message.content[:500],
        "draft_reply": draft_reply[:500],
        "escalated_at": timezone.now().isoformat(),
    }
    conversation.context = context
    conversation.save(update_fields=["ai_handling", "status", "context", "updated_at"])
    logger.info("Conversation %s escalated to human (confidence=%.2f)", conversation.id, confidence)

    # Create a notification for the user
    try:
        from apps.notifications.models import Notification
        Notification.objects.create(
            user=conversation.social_account.user,
            title="WhatsApp: Conversation needs attention",
            message=f"{conversation.contact_name or 'A customer'} needs a human reply. AI confidence was too low.",
            notification_type="whatsapp_escalation",
            link=f"/whatsapp/conversation/{conversation.id}/",
        )
    except Exception as e:
        logger.warning("Failed to create escalation notification: %s", e)


# ─── Language Detection ──────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """
    Simple language detection for Kenya's main WhatsApp languages.

    Uses keyword heuristics — not perfect, but fast and works for routing.
    The AI model handles actual language matching in its reply.
    """
    if not text:
        return ""

    text_lower = text.lower()

    # Common Sheng words/phrases (Nairobi urban slang — mix of Swahili + English + more)
    sheng_markers = [
        "sasa", "niaje", "poa", "maze", "manze", "aje", "buda", "dem",
        "mathree", "mbuzi", "cheki", "dishi", "fiti", "iko", "sawa sawa",
        "wasee", "nini", "rada", "chapaa", "doh", "gashui", "mharo",
    ]
    # Common Swahili words
    swahili_markers = [
        "habari", "jambo", "karibu", "asante", "tafadhali", "ndio", "hapana",
        "nzuri", "sana", "rafiki", "biashara", "bei", "duka", "wateja",
        "naomba", "ninaweza", "unataka", "tunafanya", "haraka", "pole",
        "shukrani", "hujambo", "salama",
    ]

    sheng_count = sum(1 for w in sheng_markers if w in text_lower)
    swahili_count = sum(1 for w in swahili_markers if w in text_lower)

    if sheng_count >= 2:
        return "sheng"
    if swahili_count >= 2:
        return "sw"
    if sheng_count == 1 or swahili_count == 1:
        # Mixed — check if mostly English
        words = text_lower.split()
        if len(words) > 3:
            return "en"  # Default to English for mixed messages
        return "sw" if swahili_count else "sheng"

    return "en"  # Default


# ─── Prompt Building ─────────────────────────────────────────────────────────

def _build_system_prompt(profile, conversation):
    """Build the system prompt with brand context and conversation rules."""
    brand_name = profile.company_name or profile.user.get_full_name() or "the business"
    language_instruction = _get_language_instruction(conversation.language)

    parts = [
        f"You are the AI customer engagement assistant for {brand_name} on WhatsApp.",
        f"You respond to customer messages in the brand's voice.",
        "",
        "## BRAND CONTEXT",
        f"Business: {brand_name}",
    ]
    if profile.industry:
        parts.append(f"Industry: {profile.get_industry_display()}")
    if profile.brand_voice:
        parts.append(f"Brand voice: {profile.brand_voice}")
    if profile.tone_attributes:
        parts.append(f"Tone: {', '.join(profile.tone_attributes)}")
    if profile.target_audience:
        parts.append(f"Target audience: {profile.target_audience}")
    if profile.key_offerings:
        offerings = profile.key_offerings
        if isinstance(offerings, list):
            offerings = ", ".join(offerings)
        parts.append(f"Products/Services: {offerings}")
    if profile.brand_restrictions:
        parts.append(f"\n## RESTRICTIONS\n{profile.brand_restrictions}")

    parts.extend([
        "",
        "## CONVERSATION RULES",
        language_instruction,
        "- Keep replies concise — WhatsApp is a chat, not an email. 1-3 short paragraphs max.",
        "- Use emojis naturally (not excessively) — they're expected on WhatsApp.",
        "- If asked about pricing, provide it if you know it. If unsure, say you'll confirm.",
        "- If the customer is angry or complaining, be empathetic first, solve second.",
        "- If you genuinely don't know the answer, say so honestly and offer to connect them with the team.",
        "- NEVER make up product details, prices, or availability that you don't know.",
        "- For orders/purchases, guide them but don't confirm transactions you can't fulfill.",
        "",
        "## RESPONSE FORMAT",
        "Respond in JSON with these fields:",
        '  "reply": "Your WhatsApp reply text"',
        '  "confidence": 0.0-1.0 (how confident are you this reply is correct and helpful?)',
        '  "reasoning": "Brief internal note on why you chose this reply"',
        '  "action": "reply" | "escalate" | "no_reply"',
        "",
        "Set action to 'escalate' if:",
        "- Customer is very angry/upset and needs human touch",
        "- Question requires access to systems you don't have (order status, account changes)",
        "- Customer explicitly asks for a human",
        "- Topic is sensitive (refunds, legal, personal data requests)",
        "",
        "Set action to 'no_reply' if:",
        "- Message is just a reaction emoji",
        "- Message is a 'thanks' or 'ok' that doesn't need a response",
    ])

    # Add conversation context if available
    context = conversation.context or {}
    if context.get("product_interests"):
        parts.append(f"\nCustomer's product interests: {context['product_interests']}")
    if conversation.tags:
        parts.append(f"Customer tags: {', '.join(conversation.tags)}")

    return "\n".join(parts)


def _build_conversation_prompt(recent_messages, current_message, conversation):
    """Build the user prompt with conversation history."""
    parts = ["## CONVERSATION HISTORY"]

    for msg in recent_messages[:-1]:  # All except the current message
        direction = "Customer" if msg.direction == "inbound" else "Business"
        ai_tag = " [AI]" if msg.is_ai_generated else ""
        parts.append(f"{direction}{ai_tag}: {msg.content[:500]}")

    parts.extend([
        "",
        "## NEW MESSAGE (respond to this)",
        f"Customer: {current_message.content}",
    ])

    if current_message.interactive_data:
        parts.append(f"[Interactive data: {json.dumps(current_message.interactive_data)[:200]}]")

    if current_message.message_type != "text":
        parts.append(f"[Message type: {current_message.get_message_type_display()}]")

    return "\n".join(parts)


def _get_language_instruction(language: str) -> str:
    """Get language-specific instructions for the AI."""
    instructions = {
        "en": "- Respond in English.",
        "sw": "- Respond in Swahili. Use proper Kiswahili — the customer prefers Swahili.",
        "sheng": "- Respond in Sheng (Nairobi urban slang — mix of Swahili, English, and street language). Keep it natural and relatable.",
        "unknown": "- Detect the customer's language from their message and respond in the SAME language. If mixed, match their style.",
    }
    return instructions.get(language, instructions["unknown"])
